"""Turn NLS export text into a short client-readable summary."""
import re
from html import escape

SKIP = (
    r'^\s*/', r'\b1159\b', r'longitudinal', r'section of', r'front view',
    r'\bcut\b', r'page\s+\d+', r'\.pdf\b', r'default\d',
)
FRIENDLY = [
    ('gall', 'Gallbladder & bile flow', 'The scan marked extra load around the gallbladder and bile flow. Heavy or fried meals often sit too long when this pattern is up. Smaller meals and bitter greens are the usual first step.'),
    ('bile', 'Gallbladder & bile flow', 'Bile-flow patterns showed up. That can mean fats feel heavy. Go easy on large fatty meals until things settle.'),
    ('dyskinesia', 'Gallbladder movement', 'Gallbladder movement was flagged. This is a wellness pattern, not a surgery note. Focus on meal timing and bitter foods.'),
    ('lymph', 'Lymph & drainage', 'Drainage points were marked. Think congestion or slow recovery \u2014 not a list of node names. Walking, hydration, and movement are simple supports.'),
    ('nodi', 'Lymph & drainage', 'Lymph drainage showed a mild load. Keep fluids up and move daily.'),
    ('kidney', 'Kidneys & fluid balance', 'Kidney-related pages were in the scan file. Hydration and steady salt intake matter more than the slice titles.'),
    ('renal', 'Kidneys & fluid balance', 'Fluid-balance patterns were noted. Sip water through the day rather than a large amount at night.'),
    ('liver', 'Liver & detox load', 'Liver-related markers were active. Alcohol, ultra-processed snacks, and late heavy dinners add load.'),
    ('detox', 'Liver & detox load', 'Detox pathways looked busy. Support with water, fiber, and a shorter evening eating window.'),
    ('intestin', 'Digestion', 'The gut showed extra signal. Simple meals, cooked vegetables, and less sugar usually help this pattern.'),
    ('digest', 'Digestion', 'Digestion was part of the scan picture. Chew well and keep snack grazing down.'),
    ('stomach', 'Digestion', 'Stomach load showed up. Avoid large drinks with meals if you bloat easily.'),
    ('candida', 'Yeast / sugar load', 'A yeast-and-sugar pattern is in the scan. Cut soda, juice, and dessert for a stretch and see how you feel.'),
    ('pylori', 'Stomach lining', 'A stomach-lining pattern was marked. Discuss testing with your clinician if you have burning or reflux.'),
    ('colon', 'Lower gut', 'The lower gut was flagged. Fiber from vegetables plus water is the first lever.'),
    ('immune', 'Immune load', 'Immune markers were active. Sleep and a lower-sugar week are the practical moves.'),
    ('thyroid', 'Thyroid & energy', 'Thyroid-related signal appeared. Get a standard thyroid blood panel if you have not in the last year.'),
    ('adren', 'Stress reserve', 'Stress-reserve markers were up. Earlier nights help more than extra caffeine.'),
    ('stress', 'Stress reserve', 'Stress load is part of this scan. Keep evenings dim and meals earlier.'),
    ('nervous', 'Nervous system', 'The nervous system showed strain. Short walks and a consistent bedtime are the baseline.'),
]

def _systems(raw):
    text = (raw or '').lower()
    found, seen = [], set()
    for key, title, blurb in FRIENDLY:
        if key in text and title not in seen:
            seen.add(title)
            found.append((title, blurb))
    if not found:
        found = [('Overall pattern', 'The scan was processed. Focus on sleep, protein, vegetables, and fewer packaged snacks while we refine the picture.')]
    return found[:8]

def client_report_html(raw_data, client_name='Client', title='Scan report'):
    first = escape((client_name or 'Client').split()[0] or 'there')
    cards = ''.join('<article class="plain-card"><h4>%s</h4><p>%s</p></article>' % (escape(t), escape(b)) for t, b in _systems(raw_data))
    return ('<style>.plain-scan{max-width:720px}.plain-card{background:#f7faf7;border:1px solid #d7e5d7;border-radius:12px;padding:.9rem 1rem;margin:.65rem 0}.plain-card h4{margin:0 0 .35rem;color:#1b4332}.plain-card p{margin:0;color:#334;line-height:1.45}</style>'
            '<section class="plain-scan"><h3>What this scan is saying</h3>'
            '<p>Hi %s. This is a plain-language read of your bioenergetic scan \u2014 not a diagnosis and not a list of machine codes.</p>'
            '%s<p style="color:#667;font-size:.9rem;">Device page names, slice titles, and raw percentages stay in the admin file.</p></section>' % (first, cards))
