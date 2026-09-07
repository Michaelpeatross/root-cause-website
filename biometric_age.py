"""Client-facing biometric age. Raw scan coefficients stay internal."""
from datetime import datetime
import re


HEAVY_CATEGORIES = {
    'Digestive & Gut',
    'Immune & Microbial',
    'Hormonal & Endocrine',
    'Nervous & Stress',
}


def extract_calendar_age(raw_data, extra_text=''):
    """Pull calendar age from scan header or intake text. None if unknown."""
    blob = f'{raw_data or ""}\n{extra_text or ""}'
    patterns = (
        r'\bAGE[:\s]+(\d{1,3})\b',
        r'\bAge[:\s]+(\d{1,3})\b',
        r'\b(\d{1,3})\s*years?\s*old\b',
        r'\bcalendar age[:\s]+(\d{1,3})\b',
        r'\bbirthday[:\s]+\d{1,2}[/-]\d{1,2}[/-](\d{2,4})\b',
    )
    for pat in patterns:
        match = re.search(pat, blob, re.I)
        if not match:
            continue
        value = match.group(1)
        if pat.endswith(r'(\d{2,4})\b') and '/' not in pat[:20]:
            year = int(value)
            if year < 100:
                year += 1900 if year > 30 else 2000
            age = datetime.utcnow().year - year
            if 5 <= age <= 110:
                return age
            continue
        age = int(value)
        if 5 <= age <= 110:
            return age
    return None


def compute_biometric_age(findings, calendar_age=None, medical_text=''):
    """
    Convert severity counts into an age offset.
    Returns a dict safe to print on the client report (no raw %).
    """
    findings = findings or []
    high = sum(1 for f in findings if f.get('severity') == 'high')
    moderate = sum(1 for f in findings if f.get('severity') == 'moderate')
    low = sum(1 for f in findings if f.get('severity') == 'low')
    heavy = {
        f.get('category')
        for f in findings
        if f.get('severity') in ('high', 'moderate') and f.get('category') in HEAVY_CATEGORIES
    }

    load = (high * 1.1) + (moderate * 0.55) + (low * 0.12)
    load += 0.8 * len(heavy)

    med = (medical_text or '').lower()
    if any(k in med for k in ('within range', 'normal', 'negative', 'non-reactive')):
        load -= 1.0
    if any(k in med for k in ('hrv', 'deep sleep', 'recovery')):
        load -= 0.4

    offset = max(-12.0, min(16.0, load - 1.5))
    offset_years = int(round(offset))

    if calendar_age:
        biometric = max(12, min(110, calendar_age + offset_years))
        delta = biometric - calendar_age
    else:
        biometric = None
        delta = offset_years

    if delta <= -3:
        direction = 'younger'
        summary = 'Scan patterns are reading younger than calendar age.'
    elif delta >= 3:
        direction = 'older'
        summary = 'Scan patterns are reading older than calendar age.'
    else:
        direction = 'matched'
        summary = 'Scan patterns are close to calendar age.'

    drivers = sorted(heavy)[:4]
    if drivers:
        summary += ' Main load is coming from ' + ', '.join(drivers).lower() + '.'
    summary += (
        ' This is a bioenergetic wellness estimate — not a clinical aging test '
        'such as PhenoAge or DNA methylation.'
    )

    return {
        'calendar_age': calendar_age,
        'biometric_age': biometric,
        'delta_years': delta,
        'direction': direction,
        'summary': summary,
        'drivers': drivers,
        'has_calendar_age': calendar_age is not None,
    }


def biometric_age_html(snapshot, client_name='Client'):
    """Client-safe HTML block. No raw scan numbers."""
    first = (client_name or 'Client').split()[0]
    if snapshot.get('has_calendar_age') and snapshot.get('biometric_age') is not None:
        cal = snapshot['calendar_age']
        bio = snapshot['biometric_age']
        delta = snapshot['delta_years']
        if delta > 0:
            diff = f'{delta} year{"s" if abs(delta) != 1 else ""} older than calendar age'
        elif delta < 0:
            diff = f'{abs(delta)} year{"s" if abs(delta) != 1 else ""} younger than calendar age'
        else:
            diff = 'matched to calendar age'
        ages = (
            f'<p><strong>Calendar age:</strong> {cal}</p>'
            f'<p><strong>Biometric age:</strong> {bio}</p>'
            f'<p><strong>Difference:</strong> {diff}</p>'
        )
    else:
        ages = (
            '<p><strong>Biometric age:</strong> calendar age was not on this scan. '
            'Add date of birth in your portal so the next report can show an exact comparison.</p>'
            f'<p>Current pattern trend: <strong>{snapshot.get("direction", "matched")}</strong>.</p>'
        )
    return (
        '<section class="report-section biometric-age-block" id="biometric-age">'
        f'<h4>Biometric Age</h4>'
        f'{ages}'
        f'<p>{snapshot.get("summary", "")}</p>'
        f'<p class="rec-note">{first}, raw scanner percentages are kept off this report on purpose.</p>'
        '</section>'
    )
