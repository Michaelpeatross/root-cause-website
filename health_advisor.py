"""Generate personalized health recommendations using Grok or local analysis."""
import base64
import json
import os
import re
import urllib.error
import urllib.request

from report_generator import _parse_lines, _recommendations
from affiliate_links import supplement_list_html, lab_list_html, enrich_html_with_affiliate_links
from document_service import parse_date_from_text

_DEFAULT_GROK_MODELS = (
    'grok-4.3',
    'grok-3',
    'grok-2-latest',
    'grok-beta',
)

_VISION_GROK_MODELS = (
    'grok-2-vision-1212',
    'grok-vision-beta',
    'grok-4.3',
)

_last_grok_error = None


def get_last_grok_error():
    """Most recent Grok API failure (for admin diagnostics)."""
    return _last_grok_error


def test_grok_connection():
    """
    Minimal Grok API ping for admin diagnostics.
    Returns (ok: bool, message: str).
    """
    api_key = (os.environ.get('XAI_API_KEY') or '').strip()
    if not api_key:
        return False, 'XAI_API_KEY is not set on this server.'
    if not api_key.startswith('xai-'):
        return False, 'XAI_API_KEY should start with "xai-" (copy the full key from console.x.ai).'

    model = _grok_model_candidates()[0]
    content = _grok_chat(
        'Reply with exactly: Grok API connected.',
        system='Reply briefly with the exact phrase requested.',
        temperature=0,
        timeout=30,
        max_model_attempts=1,
    )
    if content and 'connected' in content.lower():
        return True, f'Grok API connected successfully (model: {model}).'
    err = get_last_grok_error() or 'empty response'
    return False, err


def _grok_model_candidates():
    models = []
    env_model = (os.environ.get('XAI_MODEL') or '').strip()
    if env_model:
        models.append(env_model)
    for model in _DEFAULT_GROK_MODELS:
        if model not in models:
            models.append(model)
    return models


def _set_grok_error(message):
    global _last_grok_error
    _last_grok_error = message
    if message:
        print(f'[Root Cause Grok] {message}')


def _should_try_next_grok_model(http_code, detail):
    """Only retry another model when the current model name is invalid."""
    if http_code not in (400, 404):
        return False
    lower = (detail or '').lower()
    return 'model' in lower or 'not found' in lower


def _grok_chat(
    prompt, system='You respond with concise, accurate output.',
    temperature=0.3, timeout=40, max_model_attempts=1,
):
    global _last_grok_error
    _last_grok_error = None

    api_key = (os.environ.get('XAI_API_KEY') or '').strip()
    if not api_key:
        _set_grok_error('XAI_API_KEY is not set.')
        return None

    body = {
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': temperature,
    }

    errors = []
    models = _grok_model_candidates()[:max(1, max_model_attempts)]
    for idx, model in enumerate(models):
        payload = json.dumps({**body, 'model': model}).encode('utf-8')
        req = urllib.request.Request(
            'https://api.x.ai/v1/chat/completions',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            content = data['choices'][0]['message']['content'].strip()
            if content:
                return content
            errors.append(f'{model}: empty response')
        except urllib.error.HTTPError as exc:
            detail = ''
            try:
                detail = exc.read().decode('utf-8', errors='ignore')[:300]
            except Exception:
                pass
            errors.append(f'{model}: HTTP {exc.code} {detail or exc.reason}')
            if exc.code in (401, 403):
                break
            if idx + 1 < len(models) and _should_try_next_grok_model(exc.code, detail):
                continue
            break
        except TimeoutError as exc:
            errors.append(f'{model}: timed out after {timeout}s')
            break
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, IndexError) as exc:
            errors.append(f'{model}: {exc}')
            break

    _set_grok_error('Grok API failed — ' + '; '.join(errors[:2]))
    return None


def _grok_vision_chat(
    content_parts, system='You extract text accurately from document images.',
    temperature=0.1, timeout=60,
):
    """Multimodal Grok call for PDF page images."""
    global _last_grok_error
    _last_grok_error = None

    api_key = (os.environ.get('XAI_API_KEY') or '').strip()
    if not api_key:
        _set_grok_error('XAI_API_KEY is not set.')
        return None

    body = {
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': content_parts},
        ],
        'temperature': temperature,
    }

    env_model = (os.environ.get('XAI_VISION_MODEL') or '').strip()
    models = [env_model] if env_model else []
    for model in _VISION_GROK_MODELS:
        if model not in models:
            models.append(model)

    errors = []
    for idx, model in enumerate(models):
        payload = json.dumps({**body, 'model': model}).encode('utf-8')
        req = urllib.request.Request(
            'https://api.x.ai/v1/chat/completions',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            content = data['choices'][0]['message']['content'].strip()
            if content:
                return content
            errors.append(f'{model}: empty response')
        except urllib.error.HTTPError as exc:
            detail = ''
            try:
                detail = exc.read().decode('utf-8', errors='ignore')[:300]
            except Exception:
                pass
            errors.append(f'{model}: HTTP {exc.code} {detail or exc.reason}')
            if exc.code in (401, 403):
                break
            if idx + 1 < len(models) and _should_try_next_grok_model(exc.code, detail):
                continue
            break
        except TimeoutError:
            errors.append(f'{model}: timed out after {timeout}s')
            break
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, IndexError) as exc:
            errors.append(f'{model}: {exc}')
            break

    _set_grok_error('Grok vision failed — ' + '; '.join(errors[:2]))
    return None


def grok_extract_pdf_scan_text(pdf_path, max_pages=6, max_chars=60000):
    """
    OCR bio scan PDFs via Grok vision when normal text extraction returns nothing.
    Renders pages to images and asks Grok to return plain scan text.
    """
    try:
        import fitz
    except ImportError:
        return ''

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return ''

    if len(doc) == 0:
        doc.close()
        return ''

    page_count = min(len(doc), max_pages)
    prompt = (
        'Extract ALL visible text from these bioenergetic Full Scan PDF page images. '
        'Return plain text only — no markdown, no commentary. Preserve section headings '
        '(Full Scan, Energetic System Performance, Energetic Sensitivities, '
        'Energetic Nutritional Imbalances, Energetic Toxins, Metabolic Test Results, '
        'Personalized Client Summary, Next Steps, Balancing Remedies), marker names, '
        'percentages, and remedy details exactly as shown.'
    )

    all_text = []
    batch_size = 3
    try:
        for start in range(0, page_count, batch_size):
            content_parts = [{'type': 'text', 'text': prompt}]
            for page_idx in range(start, min(start + batch_size, page_count)):
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                png_bytes = pix.tobytes('png')
                b64 = base64.b64encode(png_bytes).decode('ascii')
                content_parts.append({
                    'type': 'image_url',
                    'image_url': {
                        'url': f'data:image/png;base64,{b64}',
                        'detail': 'high',
                    },
                })

            chunk = _grok_vision_chat(content_parts, timeout=75)
            if chunk:
                all_text.append(chunk.strip())
    finally:
        doc.close()

    combined = '\n\n'.join(all_text).strip()
    if len(combined) >= 80:
        return combined[:max_chars]
    return ''


def _local_classify_document(extracted_text, original_name):
    """Heuristic document type and date when Grok is unavailable."""
    lower = f'{(extracted_text or "").lower()} {(original_name or "").lower()}'
    parsed = parse_date_from_text(extracted_text)
    date_str = parsed.strftime('%Y-%m-%d') if parsed else None

    type_map = [
        (('lipid', 'cholesterol', 'ldl', 'hdl', 'triglyceride'), 'Lipid Panel / Cholesterol Test'),
        (('thyroid', 'tsh', ' free t3', ' free t4'), 'Thyroid Panel'),
        (('a1c', 'hemoglobin a1c', 'hba1c'), 'Hemoglobin A1C Test'),
        (('glucose', 'fasting sugar', 'blood sugar'), 'Blood Glucose Test'),
        (('cbc', 'complete blood count', 'hematocrit', 'platelet count'), 'Complete Blood Count (CBC)'),
        (('metabolic panel', 'cmp', 'bmp', 'comprehensive metabolic'), 'Comprehensive Metabolic Panel'),
        (('vitamin d', '25-hydroxy', '25-oh'), 'Vitamin D Test'),
        (('ferritin', 'iron panel', 'serum iron'), 'Iron / Ferritin Panel'),
        (('b12', 'folate', 'methylmalonic'), 'B12 / Folate Panel'),
        (('cortisol', 'estrogen', 'testosterone', 'progesterone', 'dhea'), 'Hormone Panel'),
        (('urinalysis', 'urine culture'), 'Urinalysis'),
        (('pathology', 'biopsy'), 'Pathology Report'),
        (('mri', 'ct scan', 'x-ray', 'xray', 'ultrasound', 'radiology'), 'Medical Imaging Report'),
        (('colonoscopy', 'endoscopy'), 'Procedure Report'),
        (('allergy', 'ige'), 'Allergy Test'),
    ]
    for keywords, label in type_map:
        if any(k in lower for k in keywords):
            return {'document_name': label, 'test_date': date_str}

    if 'lab' in lower or 'reference range' in lower or 'specimen' in lower:
        return {'document_name': 'Lab Results', 'test_date': date_str}
    if '[medical image' in lower or original_name.lower().endswith(
        ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.heic', '.heif')
    ):
        return {'document_name': 'Medical Image / Screenshot', 'test_date': date_str}

    clean_name = re.sub(r'[_\-]+', ' ', os.path.splitext(original_name or 'Medical document')[0]).strip()
    return {'document_name': clean_name or 'Medical document', 'test_date': date_str}


def classify_medical_document(extracted_text, original_name):
    """
    Return Grok-inferred document label and test date.
    Keys: document_name (str), test_date (YYYY-MM-DD or None).
    """
    excerpt = (extracted_text or '')[:6000]
    prompt = f"""Identify this medical document for a client health portal.

Original filename: {original_name or 'unknown'}

Document text:
{excerpt or '[No extractable text — infer from filename if possible]'}

Return JSON only, no markdown:
{{"document_name": "short descriptive name e.g. Lipid Panel Blood Test", "test_date": "YYYY-MM-DD or null"}}

Use the test/collection/report date found in the document when possible."""

    content = _grok_chat(
        prompt,
        system='You classify medical documents. Respond with valid JSON only.',
        temperature=0.2,
    )
    if content:
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        try:
            data = json.loads(content)
            name = (data.get('document_name') or '').strip()
            date_val = data.get('test_date')
            if date_val in (None, '', 'null', 'unknown'):
                date_val = None
            elif isinstance(date_val, str):
                date_val = date_val.strip()[:10]
            if name:
                return {'document_name': name[:200], 'test_date': date_val}
        except (json.JSONDecodeError, TypeError):
            pass

    return _local_classify_document(extracted_text, original_name)


def _local_medical_notes_html(medical_text, client_name):
    """Plain-language medical record notes when Grok is unavailable."""
    if not medical_text or len(medical_text.strip()) < 80:
        return ''
    return f"""<section class="scan-section">
  <h2>Your Medical Records — Plain English Notes</h2>
  <p class="scan-lead">A quick overview of how your uploaded lab work connects to your scan.</p>
  <div class="scan-summary">
    <p>We reviewed your uploaded medical documents and any wearable health data (Apple Watch, fitness trackers, heart rate, sleep, activity, etc.) alongside your bioenergetic scan. Share these records with your practitioner and discuss any out-of-range values at your next visit.</p>
    <p><em>Recommendations incorporate all documents you uploaded to your client portal.</em></p>
  </div>
</section>"""


def _local_recommendations_html(scan_raw, medical_text, client_name):
    """Rule-based recommendations when Grok API is unavailable."""
    findings = _parse_lines(scan_raw or '')
    high = [f for f in findings if f['severity'] == 'high']
    moderate = [f for f in findings if f['severity'] == 'moderate']

    active_cats = list({f['category'] for f in high + moderate})
    if not active_cats and findings:
        active_cats = list({f['category'] for f in findings[:6]})

    supplements, labs = _recommendations(active_cats)

    lifestyle = []
    med_lower = (medical_text or '').lower()
    scan_lower = (scan_raw or '').lower()

    if any(k in scan_lower for k in ('gut', 'stomach', 'digest', 'candida', 'intestin')):
        lifestyle.append('Prioritize whole foods, reduce processed sugar, and eat slowly at mealtimes.')
    if any(k in scan_lower for k in ('thyroid', 'adrenal', 'cortisol', 'hormone')):
        lifestyle.append('Support sleep hygiene (7–9 hours) and consistent meal timing for hormonal balance.')
    if any(k in scan_lower for k in ('stress', 'adrenal', 'nerve', 'brain')):
        lifestyle.append('Add daily stress recovery: walking, breathwork, or gentle movement.')
    if 'cholesterol' in med_lower or 'ldl' in med_lower:
        lifestyle.append('Medical records mention lipids — pair heart-healthy fats with fiber-rich vegetables.')
    if 'diabetes' in med_lower or 'a1c' in med_lower or 'glucose' in med_lower:
        lifestyle.append('Blood sugar markers noted in uploaded records — prioritize protein + fiber at each meal.')
    if not lifestyle:
        lifestyle.append('Maintain hydration, regular movement, and a consistent sleep schedule.')

    priority_lines = []
    for f in (high + moderate)[:8]:
        line = f'<li><strong>{f["label"]}</strong>'
        if f['value']:
            line += f' ({f["value"]}% resonance)'
        line += f' — focus area: {f["category"]}</li>'
        priority_lines.append(line)

    if not priority_lines:
        priority_lines.append('<li>Continue monitoring with your practitioner based on scan and uploaded records.</li>')

    supp_li = supplement_list_html(supplements[:6])
    lab_li = lab_list_html(labs[:6])
    life_li = ''.join(f'<li>{l}</li>' for l in lifestyle)

    doc_note = ''
    if medical_text and len(medical_text.strip()) > 50:
        doc_note = '<p><em>Recommendations incorporate all your uploaded medical documents <strong>and any wearable health data</strong> (Apple Watch, fitness trackers, etc.).</em></p>'

    return f"""<section class="report-section ai-section">
  <h3>🧠 Personalized Health Options for {client_name}</h3>
  {doc_note}
  <h4>Priority Focus Areas</h4>
  <ul>{''.join(priority_lines)}</ul>
  <h4>Suggested Supplements</h4>
  <ul>{supp_li}</ul>
  <h4>Lifestyle &amp; Nutrition</h4>
  <ul>{life_li}</ul>
  <h4>Labs to Discuss</h4>
  <ul>{lab_li}</ul>
  <p class="rec-note">Educational guidance only — not medical advice. Consult your healthcare provider before changes.</p>
</section>"""


def _local_original_scan_analysis_html(scan_raw, client_name):
    """Readable original scan summary when Grok is unavailable."""
    from scan_template import _scan_body_text, _find_sections, _clean_readable_text

    first = (client_name or 'Client').split()[0]
    body = _scan_body_text(scan_raw or '')
    sections = _find_sections(body) if body else {}
    summary = _clean_readable_text(sections.get('summary', ''))
    next_steps = _clean_readable_text(sections.get('next_steps', ''))

    paragraphs = []
    if summary:
        for chunk in re.split(r'\n\s*\n', summary):
            chunk = chunk.strip()
            if chunk:
                paragraphs.append(chunk)
    if not paragraphs:
        findings = _parse_lines(scan_raw or '')
        priority = [f for f in findings if f['severity'] in ('high', 'moderate')][:6]
        if priority:
            items = ''.join(
                f'<li><strong>{f["label"]}</strong>'
                + (' — noted as a focus area' if not f.get('value') else '')
                + '</li>'
                for f in priority
            )
            body_html = (
                f'<p>{first}, your bioenergetic scan highlighted several areas worth '
                f'attention. The key patterns are summarized below.</p>'
                f'<ul>{items}</ul>'
            )
        else:
            body_html = (
                f'<p>{first}, your bioenergetic scan has been processed. '
                f'Review the scan report sections above for your full results.</p>'
            )
    else:
        body_html = ''.join(f'<p>{p}</p>' for p in paragraphs[:4])

    if next_steps and len(body_html) < 1200:
        step_lines = [
            ln.strip() for ln in next_steps.split('\n') if ln.strip() and not ln.strip().startswith('→')
        ][:4]
        if step_lines:
            body_html += '<h4 style="margin-top:1rem;">Suggested next steps from your scan</h4><ul>'
            body_html += ''.join(f'<li>{ln}</li>' for ln in step_lines)
            body_html += '</ul>'

    return f"""<section class="scan-section">
  <h2>Original Scan Analysis</h2>
  <p class="scan-lead">A plain-language overview of what your bioenergetic scan found.</p>
  <div class="scan-summary">{body_html}</div>
</section>"""


def _grok_original_scan_analysis(scan_raw, client_name, client_email):
    """Grok analysis of the bio scan only — no medical documents."""
    api_key = os.environ.get('XAI_API_KEY')
    if not api_key:
        return None

    prompt = f"""You are a holistic health advisor for Root Cause Bioenergetics.
Write the ORIGINAL scan analysis for a client's bioenergetic Full Scan.
Use ONLY the scan data below — no medical lab documents are included yet.

Client: {client_name} ({client_email})

BIOENERGETIC SCAN DATA:
{scan_raw[:8000]}

Write for an average adult (8th-grade reading level).
- 3–5 short paragraphs or clear sections.
- For each key pattern or finding, briefly explain: What this typically tests/measures in a bioenergetic scan, and what the client's results appear to indicate (in plain language).
- Name the main body systems, sensitivities, or patterns that stood out.
- Use <strong> around important terms/pattern names so they can be interactively explained later.
- Do NOT include raw numbers or percentages.
- Do NOT recommend specific products or affiliate links.
- Address the client by first name once in the opening sentence.

Respond in HTML only (no markdown). Use exactly this structure:
<section class="scan-section">
  <h2>Original Scan Analysis</h2>
  <p class="scan-lead">A plain-language overview of what your bioenergetic scan found, including what key areas test for and what your results suggest.</p>
  <div class="scan-summary">
    <p>...</p>
  </div>
</section>"""

    content = _grok_chat(
        prompt,
        system='You write warm, clear wellness education in simple HTML. No jargon.',
        temperature=0.35,
        timeout=45,
        max_model_attempts=1,
    )
    if not content:
        return None
    content = re.sub(r'^```html\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    if '<section' in content:
        return content
    return (
        '<section class="scan-section">'
        '<h2>Original Scan Analysis</h2>'
        f'<div class="scan-summary"><p>{content}</p></div>'
        '</section>'
    )


def _grok_full_scan_medical_notes(scan_raw, medical_text, client_name, client_email):
    """Plain-English medical record notes styled like the Full Scan PDF."""
    if not medical_text or len(medical_text.strip()) < 80:
        return ''

    prompt = f"""You are writing a short, easy-to-read section for a bioenergetic Full Scan report.
The scan PDF already contains the main results, summaries, next steps, and remedy products.
Your job is ONLY to explain how the client's uploaded medical lab work connects to their scan — in everyday language.

Client: {client_name}

SCAN EXCERPT (for context only):
{scan_raw[:8000]}

CLIENT MEDICAL DOCUMENTS AND WEARABLE DATA (Apple Watch, fitness trackers, heart rate, sleep, steps, etc.):
{medical_text[:40000]}

Write for an average adult with no medical background.
- Use short sentences and common words (8th-grade reading level).
- No bullet lists, no affiliate links, no product recommendations.
- 2–4 short paragraphs maximum.
- Address the client by first name once in the opening sentence.
- Do not repeat content that belongs in a scan summary (systems, sensitivities, remedies).

Respond in HTML only (no markdown). Use exactly this structure:
<section class="scan-section">
  <h2>Your Medical Records — Plain English Notes</h2>
  <p class="scan-lead">How your uploaded lab work relates to what showed up on your scan.</p>
  <div class="scan-summary">
    <p>...</p>
  </div>
</section>"""

    content = _grok_chat(
        prompt,
        system='You write warm, clear wellness education in simple HTML. No jargon.',
        temperature=0.35,
        timeout=45,
        max_model_attempts=1,
    )
    if not content:
        return ''
    content = re.sub(r'^```html\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    if '<section' in content:
        return content
    return (
        '<section class="scan-section">'
        '<h2>Your Medical Records — Plain English Notes</h2>'
        f'<div class="scan-summary"><p>{content}</p></div>'
        '</section>'
    )


def _grok_recommendations(scan_raw, medical_text, client_name, client_email):
    """Call xAI Grok API for personalized recommendations."""
    api_key = os.environ.get('XAI_API_KEY')
    if not api_key:
        return None

    prompt = f"""You are a holistic health advisor for Root Cause Bioenergetics.
Analyze the client's bioenergetic scan data (may include text pasted by the practitioner
and/or text extracted from uploaded scan PDFs) plus any client medical documents.
Provide clear, actionable health options (not diagnoses).

Client: {client_name} ({client_email})

BIOENERGETIC SCAN DATA (paste + PDF extracts):
{scan_raw[:12000]}

CLIENT MEDICAL DOCUMENTS (all uploaded labs, blood work, medical records, AND wearable health data from Apple Watch / fitness trackers / health monitors — any date):
{medical_text[:50000] if medical_text else 'None uploaded yet.'}

Cross-reference scan findings with lab values across the client's full uploaded medical history.
Note trends over time when multiple documents are present.
For key scan findings, briefly note what the bioenergetic pattern tests for and what the results + labs together suggest.
For supplements, recommend specific affordable products with Amazon links where possible.
For blood tests and labs: Suggest relevant standard blood tests based on the scan findings (e.g. Thyroid panel, Vitamin D, Comprehensive Metabolic Panel, Hormone panel, etc. if the data indicates). Always direct to order them through GoodLabs (https://goodlabs.com/book-tests) and discuss the exact panels with their practitioner. Use the general link.
Do not mention Quest, LabCorp, Any Lab Test Now, Walk-In Lab, Ulta Lab Tests,
or any other lab provider.

Respond in HTML only (no markdown). Use this structure:
<section class="report-section ai-section">
  <h3>Personalized Health Options</h3>
  <h4>Priority Focus Areas</h4><ul><li>...</li></ul>
  <h4>Suggested Supplements</h4><ul><li>...</li></ul>
  <h4>Lifestyle & Nutrition</h4><ul><li>...</li></ul>
  <h4>Labs to Discuss With Your Doctor</h4><ul><li>...</li></ul>
  <p class="rec-note">Educational guidance only — not medical advice.</p>
</section>

Be specific to this client's data. Keep lists concise (3-6 items each). Use <strong> on important test/pattern names."""

    content = _grok_chat(
        prompt,
        system='You provide wellness education in clean HTML fragments.',
        temperature=0.4,
        timeout=50,
        max_model_attempts=1,
    )
    if content:
        content = re.sub(r'^```html\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        if '<section' in content:
            return content
        return f'<section class="report-section ai-section">{content}</section>'
    return None


def get_health_recommendations(
    scan_raw, medical_text, client_name, client_email, full_scan_mode=False,
):
    """Return HTML block with personalized health recommendations."""
    has_medical = bool(medical_text and len(medical_text.strip()) >= 80)

    if full_scan_mode:
        if has_medical:
            grok_html = _grok_full_scan_medical_notes(
                scan_raw, medical_text, client_name, client_email,
            )
            if grok_html:
                return grok_html, 'grok'
            local = _local_medical_notes_html(medical_text, client_name)
            if local:
                return local, 'local'
        grok_html = _grok_original_scan_analysis(scan_raw, client_name, client_email)
        if grok_html:
            return grok_html, 'grok'
        return _local_original_scan_analysis_html(scan_raw, client_name), 'local'

    grok_html = _grok_recommendations(scan_raw, medical_text, client_name, client_email)
    if grok_html:
        return enrich_html_with_affiliate_links(grok_html), 'grok'
    return _local_recommendations_html(scan_raw, medical_text, client_name), 'local'


def generate_wearable_summary(wearable_text: str, client_email: str) -> str:
    """Use Grok to auto-generate a concise, actionable summary of uploaded wearable/health monitor data.
    Returns plain text summary or empty string on failure.
    """
    if not wearable_text or len(wearable_text.strip()) < 40:
        return ""

    excerpt = wearable_text[:12000]  # keep context reasonable

    prompt = f"""You are a helpful wellness analyst for Root Cause Bioenergetics.

Analyze the following wearable / health monitor data (Apple Watch, fitness tracker, etc.) and produce a clear, plain-language summary.

Focus on:
- Key trends in heart rate (resting, average, variability if present)
- Sleep patterns and quality
- Activity / steps / movement levels
- Any notable patterns, outliers, or correlations
- How this data might relate to stress, recovery, energy, or bioenergetic findings

Keep it concise (3–6 short paragraphs). Be encouraging but factual. Do not give medical advice or diagnosis.

WEARABLE DATA:
{excerpt}

CLIENT: {client_email}
"""

    content = _grok_chat(
        prompt,
        system="You summarize wearable health data clearly for clients. Stay educational and non-diagnostic.",
        temperature=0.25,
        timeout=45,
    )

    if content:
        return content.strip()

    return ""