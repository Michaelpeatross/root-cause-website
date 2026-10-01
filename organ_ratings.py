"""Plain-language organ ratings from a scan file. No raw coefficients."""
import re
from html import escape

# title, keywords, finding, first step, clinician question
ORGANS = (
    ('Lungs', ('lung', 'pulmon', 'bronch', 'pleura', 'alveol'),
     'Breathing patterns were among the louder signals. This is not a lung test.',
     'Notice indoor air and how stairs feel. Mention ongoing shortness of breath to a clinician.',
     'Shortness of breath or a cough should be checked on its own. Which basic breathing questions belong at a visit, separate from this scan?'),
    ('Kidneys', ('kidney', 'renal', 'nephro'),
     'Kidney patterns were louder than most other organs. This is not a kidney-function test.',
     'Sip water through the day rather than a large amount at night.',
     'Should I have a basic kidney panel (creatinine, eGFR) if I have not had one this year?'),
    ('Brain and nerves', ('brain', 'cerebr', 'nerve', 'nervus', 'pituitary', 'hypothalam'),
     'Brain and nerve patterns were among the stronger signals. This is load, not a diagnosis.',
     'Keep caffeine to the morning and try an earlier bedtime for several nights.',
     'Sleep and mental load seem tied to how I feel. What should I track before any further testing?'),
    ('Lymph', ('lymph',),
     'Drainage patterns were busy on this scan. This is not an infection test.',
     'Walk daily and spread water through the day.',
     'I feel puffy or slow to recover. What symptoms should make me come in, versus walking and drinking more water?'),
    ('Intestines', ('intestin', 'colon', 'bowel', 'duoden', 'ileum', 'rectum'),
     'The intestinal pattern was louder than many other organs. This is not a colonoscopy result.',
     'Simpler meals, chew well, and cut constant snacking for a week.',
     'Meals feel heavy. What symptoms would make a stool test reasonable, versus a simpler-meals trial first?'),
    ('Stomach', ('stomach', 'gastric', 'esophag'),
     'Stomach patterns showed extra signal. This is not an ulcer test.',
     'Smaller meals, and less to drink with the meal if you bloat easily.',
     'If I have burning or reflux, is an H. pylori test worth ordering, separate from this scan?'),
    ('Pancreas', ('pancrea',),
     'Pancreas patterns were part of the louder group. This is not a blood-sugar diagnosis.',
     'Pair carbs with protein and skip sweet drinks for a week.',
     'Is a standard glucose or A1C check due, separate from this wellness scan?'),
    ('Liver', ('liver', 'hepat'),
     'Liver patterns were active. This is not a liver-disease test.',
     'Skip alcohol and late heavy dinners for a week and see how mornings feel.',
     'Which liver labs, if any, match late heavy meals or alcohol, separate from this scan?'),
    ('Heart', ('heart', 'cardiac', 'myocard', 'coronar'),
     'Heart patterns were in the middle of the pack. This is not an EKG or a stress test.',
     'Take a daily walk and keep ultra-processed snacks down this week.',
     'For my age, which basic heart checks are already appropriate, separate from this scan?'),
    ('Adrenals', ('adrenal', 'suprarenal'),
     'Adrenal patterns were quieter than the louder organs. This is not a hormone lab.',
     'An earlier bedtime beats extra caffeine.',
     'Sleep and caffeine seem to drive my energy. What should I track before hormone testing?'),
    ('Thyroid', ('thyroid', 'thyreoid', 'parathyroid'),
     'Thyroid patterns were quieter on this scan. This is not a thyroid blood test.',
     'Ask your clinician whether a standard thyroid panel is due.',
     'Is a standard thyroid panel due, separate from this wellness scan?'),
    ('Skin', (' skin', 'dermal', 'epiderm', 'cutis'),
     'Skin patterns were quieter than the louder organs. This is not a skin diagnosis.',
     'Keep showers shorter and notice whether sugar-heavy days line up with flare-ups.',
     'If I have a rash or a spot that is changing, that needs a look in person. What else is worth mentioning?'),
    ('Gallbladder', ('gallbladder', 'gall bladder', 'bile', 'biliar', 'cholecyst'),
     'Gallbladder patterns were among the quieter organs on this scan. This is not a gallbladder test.',
     'Smaller meals, and go easy on fried food while you watch how you feel.',
     'Fatty meals sit heavy. Is a standard liver panel worth ordering, separate from this scan?'),
)


def _values_for(lines, keys):
    vals = []
    for line in lines:
        low = ' ' + line.lower()
        if not any(k in low for k in keys):
            continue
        match = re.search(r'D\s*=\s*(\d+(?:\.\d+)?)', line)
        if not match:
            continue
        value = float(match.group(1))
        if value <= 1:
            value *= 100
        if 0 <= value <= 100:
            vals.append(value)
    return vals


def _scan_lines(raw_data):
    lines = []
    for raw in (raw_data or '').splitlines():
        line = raw.strip()
        if len(line) < 4:
            continue
        if re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', line) and re.search(r'\b\d{3,5}\b', line):
            continue
        lines.append(line)
    return lines


def rate_organs(raw_data, calendar_age=None, biometric_age=None):
    """Return every major organ, loudest first. Ratings only, no machine numbers."""
    lines = _scan_lines(raw_data)
    measured = []
    for title, keys, why, step, question in ORGANS:
        vals = _values_for(lines, keys)
        if len(vals) < 3:
            measured.append((None, title, why, step, question))
            continue
        top = sorted(vals, reverse=True)[:12]
        measured.append((sum(top) / len(top), title, why, step, question))
    known = [row[0] for row in measured if row[0] is not None]
    if not known:
        return []
    lo, hi = min(known), max(known)
    span = hi - lo or 1
    if calendar_age and biometric_age:
        year_span = max(0, int(biometric_age) - int(calendar_age))
    else:
        year_span = 12
    rows = []
    for avg, title, why, step, question in measured:
        if avg is None:
            rating, band, organ_age = 84, 'Steady', calendar_age
        else:
            ratio = (avg - lo) / span
            rating = int(round(86 - ratio * 38))
            rating = max(42, min(92, rating))
            if calendar_age:
                organ_age = int(calendar_age) + int(round(ratio * year_span))
            else:
                organ_age = None
            if rating >= 78:
                band = 'Steady'
            elif rating >= 66:
                band = 'Mild load'
            elif rating >= 54:
                band = 'Moderate load'
            else:
                band = 'Higher load'
        rows.append({
            'title': title,
            'rating': rating,
            'band': band,
            'organ_age': organ_age,
            'why': why,
            'step': step,
            'question': question,
        })
    rows.sort(key=lambda row: (row['rating'], row['title']))
    return rows


def priority_items(raw_data, limit=3, calendar_age=None, biometric_age=None):
    rows = rate_organs(raw_data, calendar_age=calendar_age, biometric_age=biometric_age)
    loud = [row for row in rows if row['band'] != 'Steady'] or rows
    return [(row['title'], row['why'], row['step']) for row in loud[:limit]]


def organ_board_html(raw_data, calendar_age=None, biometric_age=None, client_name='Client'):
    rows = rate_organs(raw_data, calendar_age=calendar_age, biometric_age=biometric_age)
    if not rows:
        return ''
    first = escape(((client_name or 'Client').split() or ['there'])[0])
    age_note = ''
    if calendar_age:
        age_note = ' Calendar age on this scan is %s.' % int(calendar_age)
    head = (
        '<h3>Major organs</h3>'
        '<p>' + first + ', every major organ is listed below, loudest first. '
        'The rating is higher when that organ was quieter. The age is a bioenergetic estimate beside calendar age, '
        'not a clinical organ test and not a diagnosis.' + age_note + '</p>'
    )
    body = []
    for row in rows:
        age = str(row['organ_age']) if row['organ_age'] else '—'
        body.append(
            '<tr><td><strong>' + escape(row['title']) + '</strong></td>'
            '<td>' + str(row['rating']) + ' · ' + escape(row['band']) + '</td>'
            '<td>' + age + '</td>'
            '<td>' + escape(row['why']) + '</td></tr>'
        )
    return (
        head
        + '<table class="organ-board"><thead><tr><th>Organ</th><th>Rating</th><th>Age</th><th>What stood out</th></tr></thead><tbody>'
        + ''.join(body)
        + '</tbody></table>'
        '<p class="rec-note">Higher rating means quieter on this scan. Organ age is not a lab result.</p>'
    )
