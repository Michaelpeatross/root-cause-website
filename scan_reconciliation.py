"""Compare bioenergetic scan findings with uploaded blood tests and lab work."""
import re

from health_advisor import _grok_chat

NEGATIVE_LAB_PHRASES = (
    'negative', 'non-reactive', 'non reactive', 'not detected', 'not found',
    'within normal', 'normal range', 'no evidence', 'absent', 'undetected',
)

CONDITION_CHECKS = (
    ('Hepatitis', ('hepatitis', 'hep b', 'hep c', 'hbv', 'hcv', 'hepat')),
    ('Thyroid imbalance', ('thyroid', 'tsh', 'hypothyroid', 'hyperthyroid')),
    ('Diabetes / blood sugar', ('diabetes', 'a1c', 'hba1c', 'glucose', 'blood sugar')),
    ('Lyme disease', ('lyme', 'borrelia')),
    ('Candida / yeast', ('candida', 'yeast overgrowth')),
    ('H. pylori', ('h. pylori', 'h pylori', 'helicobacter')),
    ('Anemia', ('anemia', 'anaemia', 'low hemoglobin', 'low ferritin')),
    ('Vitamin D deficiency', ('vitamin d', 'low vitamin d', '25-oh')),
    ('B12 deficiency', ('b12', 'vitamin b12', 'cobalamin')),
    ('High cholesterol', ('cholesterol', 'ldl', 'lipid panel')),
)


def _scan_mentions(text, keywords):
    lower = (text or '').lower()
    return any(k in lower for k in keywords)


def _blood_negative_for(text, keywords):
    lower = (text or '').lower()
    if not _scan_mentions(lower, keywords):
        return False
    for kw in keywords:
        idx = lower.find(kw)
        while idx != -1:
            window = lower[max(0, idx - 80): idx + 120]
            if any(neg in window for neg in NEGATIVE_LAB_PHRASES):
                return True
            idx = lower.find(kw, idx + 1)
    return False


def _blood_positive_for(text, keywords):
    lower = (text or '').lower()
    if not _scan_mentions(lower, keywords):
        return False
    if _blood_negative_for(text, keywords):
        return False
    positive_hints = ('positive', 'reactive', 'elevated', 'high', 'low', 'abnormal', 'out of range')
    for kw in keywords:
        idx = lower.find(kw)
        while idx != -1:
            window = lower[max(0, idx - 60): idx + 100]
            if any(h in window for h in positive_hints):
                return True
            idx = lower.find(kw, idx + 1)
    return _scan_mentions(lower, keywords)


def _local_reconciliation(scan_raw, medical_text, client_name):
    """Rule-based scan vs blood test comparison when Grok is unavailable."""
    adjusted = []
    confirmed = []
    scan_only = []

    for label, keywords in CONDITION_CHECKS:
        on_scan = _scan_mentions(scan_raw, keywords)
        if not on_scan:
            continue
        if _blood_negative_for(medical_text, keywords):
            adjusted.append({
                'name': label,
                'note': (
                    f'Showed on your bioenergetic scan, but uploaded blood work '
                    f'does not confirm {label.lower()}. Your updated analysis '
                    f'prioritizes the lab results.'
                ),
            })
        elif _blood_positive_for(medical_text, keywords):
            confirmed.append({
                'name': label,
                'note': f'Your scan and uploaded blood work both reference {label.lower()}.',
            })
        else:
            scan_only.append({
                'name': label,
                'note': (
                    f'Resonated on your scan. No matching blood test was found in '
                    f'uploaded records — consider conventional labs to verify.'
                ),
            })

    return _build_reconciliation_html(adjusted, confirmed, scan_only, client_name, '')


def _items_html(items, default_note=''):
    if not items:
        return '<p class="scan-muted">None identified.</p>'
    parts = []
    for item in items:
        name = item if isinstance(item, str) else item.get('name', '')
        note = default_note if isinstance(item, str) else item.get('note', default_note)
        parts.append(
            f'<li><strong>{name}</strong>'
            + (f'<br><span class="reconcile-note">{note}</span>' if note else '')
            + '</li>'
        )
    return f'<ul class="reconcile-list">{"".join(parts)}</ul>'


def _build_reconciliation_html(adjusted, confirmed, scan_only, client_name, updated_summary):
    first = (client_name or 'Client').split()[0]
    summary = updated_summary or (
        f'{first}, we compared your original bioenergetic scan with uploaded blood '
        f'work and lab results. Items listed under <strong>Adjusted</strong> appeared '
        f'on the scan but were not confirmed by your labs. Your report below reflects '
        f'those updates.'
    )
    return (
        '<section class="scan-section blood-reconciliation" id="blood-reconciliation">'
        '<h2>Scan &amp; Blood Test Comparison</h2>'
        '<p class="scan-lead">Your original bioenergetic scan compared with blood tests '
        'and lab records you uploaded.</p>'
        '<div class="reconcile-grid">'
        '<div class="reconcile-panel reconcile-adjusted">'
        '<h3>Adjusted (scan vs blood work differ)</h3>'
        f'{_items_html(adjusted)}'
        '</div>'
        '<div class="reconcile-panel reconcile-confirmed">'
        '<h3>Confirmed by blood work</h3>'
        f'{_items_html(confirmed)}'
        '</div>'
        '<div class="reconcile-panel reconcile-scan-only">'
        '<h3>On scan only (no matching lab uploaded)</h3>'
        f'{_items_html(scan_only)}'
        '</div>'
        '</div>'
        '<div class="scan-summary reconcile-summary">'
        f'<p>{summary}</p>'
        '</div>'
        '</section>'
    )


def _build_updated_ai_html(updated_summary, client_name):
    first = (client_name or 'Client').split()[0]
    body = updated_summary or (
        f'{first}, your personalized notes have been updated to reflect uploaded '
        f'blood work. Where lab results differ from the scan, the analysis follows '
        f'your blood tests.'
    )
    return (
        '<section class="scan-section">'
        '<h2>Updated Analysis (Blood Tests Applied)</h2>'
        '<p class="scan-lead">Personalized notes after comparing your scan with '
        'uploaded lab work.</p>'
        f'<div class="scan-summary"><p>{body}</p></div>'
        '</section>'
    )


def _parse_grok_sections(content):
    """Split Grok HTML into reconciliation block and updated analysis."""
    content = re.sub(r'^```html\s*', '', content or '')
    content = re.sub(r'\s*```$', '', content)
    recon_match = re.search(
        r'(<section[^>]*blood-reconciliation[^>]*>.*?</section>)',
        content,
        re.I | re.S,
    )
    recon_html = recon_match.group(1) if recon_match else ''
    remaining = content.replace(recon_html, '', 1).strip() if recon_html else content
    ai_html = ''
    ai_match = re.search(r'(<section[^>]*>.*?</section>)', remaining, re.I | re.S)
    if ai_match:
        ai_html = ai_match.group(1)
    elif remaining.strip():
        ai_html = f'<section class="scan-section"><div class="scan-summary"><p>{remaining}</p></div></section>'
    return recon_html, ai_html


def _grok_reconciliation(scan_raw, medical_text, client_name, client_email):
    prompt = f"""You are a clinical wellness advisor for Root Cause Bioenergetics.
Compare the client's BIOENERGETIC SCAN with their UPLOADED BLOOD TESTS and lab records.

Client: {client_name} ({client_email})

ORIGINAL BIOENERGETIC SCAN:
{scan_raw[:14000]}

UPLOADED BLOOD TESTS & LAB RECORDS:
{medical_text[:50000]}

TASK:
1. Find findings that appear on the scan but blood tests DO NOT confirm (e.g. hepatitis on scan but hepatitis negative on labs). List these under "Adjusted".
2. Find findings confirmed by BOTH scan and blood work. List under "Confirmed".
3. Find scan findings with NO matching blood test uploaded. List under "Scan only".

Write in plain language for an average adult. Be specific — name the condition and what the blood test showed.

Respond in HTML only (no markdown). Use EXACTLY this structure:

<section class="scan-section blood-reconciliation" id="blood-reconciliation">
  <h2>Scan &amp; Blood Test Comparison</h2>
  <p class="scan-lead">...</p>
  <div class="reconcile-grid">
    <div class="reconcile-panel reconcile-adjusted">
      <h3>Adjusted (scan vs blood work differ)</h3>
      <ul class="reconcile-list"><li><strong>Condition</strong><br><span class="reconcile-note">Scan showed X but blood test showed Y. Updated analysis follows labs.</span></li></ul>
    </div>
    <div class="reconcile-panel reconcile-confirmed">
      <h3>Confirmed by blood work</h3>
      <ul class="reconcile-list">...</ul>
    </div>
    <div class="reconcile-panel reconcile-scan-only">
      <h3>On scan only (no matching lab uploaded)</h3>
      <ul class="reconcile-list">...</ul>
    </div>
  </div>
  <div class="scan-summary reconcile-summary"><p>2-3 sentence overview for the client.</p></div>
</section>

<section class="scan-section">
  <h2>Updated Analysis (Blood Tests Applied)</h2>
  <p class="scan-lead">...</p>
  <div class="scan-summary"><p>2-4 short paragraphs explaining the updated personalized guidance after applying blood test results. Where scan and labs disagree, follow the labs. Address client by first name once.</p></div>
</section>

If a category has no items, write <p class="scan-muted">None identified.</p> instead of an empty list.
Do not include raw lab numbers or scan percentages — use plain descriptions only."""

    content = _grok_chat(
        prompt,
        system='You compare wellness scans with conventional lab work. Respond in clean HTML only.',
        temperature=0.3,
        timeout=90,
    )
    if not content:
        return None
    recon_html, ai_html = _parse_grok_sections(content)
    if not recon_html:
        return None
    return {
        'reconciliation_html': recon_html,
        'updated_ai_html': ai_html or _build_updated_ai_html('', client_name),
        'source': 'grok',
    }


def reconcile_scan_with_blood_tests(scan_raw, medical_text, client_name, client_email):
    """
    Compare scan with blood tests. Returns dict:
      reconciliation_html, updated_ai_html, source
    """
    if not medical_text or len(medical_text.strip()) < 80:
        return None

    grok_result = _grok_reconciliation(scan_raw, medical_text, client_name, client_email)
    if grok_result:
        return grok_result

    local_html = _local_reconciliation(scan_raw, medical_text, client_name)
    return {
        'reconciliation_html': local_html,
        'updated_ai_html': _build_updated_ai_html('', client_name),
        'source': 'local',
    }