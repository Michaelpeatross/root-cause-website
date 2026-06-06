"""Generate personalized health recommendations using Grok or local analysis."""
import json
import os
import re
import urllib.error
import urllib.request

from report_generator import _parse_lines, _recommendations
from affiliate_links import supplement_list_html, lab_list_html, enrich_html_with_affiliate_links


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
        doc_note = '<p><em>Recommendations incorporate your uploaded medical tests from the past 12 months.</em></p>'

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

CLIENT MEDICAL DOCUMENTS (labs/blood tests from past 12 months only):
{medical_text[:8000] if medical_text else 'None uploaded yet.'}

Cross-reference scan findings with recent lab values where available.
For supplements, recommend specific affordable products. For labs, mention
Any Lab Test Now, Walk-In Lab, or Ulta Lab Tests as low-cost options.

Respond in HTML only (no markdown). Use this structure:
<section class="report-section ai-section">
  <h3>Personalized Health Options</h3>
  <h4>Priority Focus Areas</h4><ul><li>...</li></ul>
  <h4>Suggested Supplements</h4><ul><li>...</li></ul>
  <h4>Lifestyle & Nutrition</h4><ul><li>...</li></ul>
  <h4>Labs to Discuss With Your Doctor</h4><ul><li>...</li></ul>
  <p class="rec-note">Educational guidance only — not medical advice.</p>
</section>

Be specific to this client's data. Keep lists concise (3-6 items each)."""

    payload = json.dumps({
        'model': os.environ.get('XAI_MODEL', 'grok-2-latest'),
        'messages': [
            {'role': 'system', 'content': 'You provide wellness education in clean HTML fragments.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.4,
    }).encode('utf-8')

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
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        content = data['choices'][0]['message']['content']
        content = re.sub(r'^```html\s*', '', content.strip())
        content = re.sub(r'\s*```$', '', content)
        if '<section' in content:
            return content
        return f'<section class="report-section ai-section">{content}</section>'
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, IndexError):
        return None


def get_health_recommendations(scan_raw, medical_text, client_name, client_email):
    """Return HTML block with personalized health recommendations."""
    grok_html = _grok_recommendations(scan_raw, medical_text, client_name, client_email)
    if grok_html:
        return enrich_html_with_affiliate_links(grok_html), 'grok'
    return _local_recommendations_html(scan_raw, medical_text, client_name), 'local'