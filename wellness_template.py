"""Reusable wellness-only report chrome.

Wraps generated scan HTML so clients see plain English first:
Your top 3 priorities, Health Scores, then collapsible raw lists.
Does not diagnose, treat, or claim allergy / disease findings.
"""
import re
from html import escape

WELLNESS_MARKER = 'id="wellness-report-chrome"'

WELLNESS_STYLES = """
<style>
.wellness-banner{background:linear-gradient(135deg,#f0f9f6,#e8f5f1);border:1px solid #b8d9cf;
border-radius:14px;padding:1.1rem 1.25rem;margin:0 0 1.25rem}
.wellness-banner h2{margin:0 0 .4rem;color:#0d5c4d;font-size:1.2rem}
.wellness-banner p{margin:.35rem 0;color:#3d5c55;line-height:1.5}
.wellness-pill-row{display:flex;flex-wrap:wrap;gap:.4rem;margin:.65rem 0 .2rem}
.wellness-pill{background:#fff;border:1px solid #c5ddd5;border-radius:999px;padding:.2rem .7rem;
font-size:.8rem;color:#0d5c4d;font-weight:600}
.wellness-theme-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.75rem;margin:0 0 1.25rem}
.wellness-theme-card{background:#fafcfb;border:1px solid #dceee8;border-radius:12px;padding:.9rem 1rem}
.wellness-theme-card h4{margin:0 0 .35rem;color:#0b3d2a}
.wellness-theme-card p{margin:0;color:#334;font-size:.92rem;line-height:1.45}
details.wellness-raw-toggle{border:1px solid #dceee8;border-radius:10px;padding:.55rem .85rem;margin:.5rem 0;background:#fff}
details.wellness-raw-toggle>summary{cursor:pointer;font-weight:600;color:#0d5c4d;list-style:none}
details.wellness-raw-toggle>summary::-webkit-details-marker{display:none}
details.wellness-raw-toggle>summary:after{content:" \u25be";font-weight:400;color:#6b857e}
details.wellness-raw-toggle[open]>summary:after{content:" \u25b4"}
.raw-count{display:inline-block;background:#e8f5f1;border-radius:999px;padding:.05rem .5rem;
font-size:.78rem;margin-left:.35rem;color:#0d5c4d}
.wellness-footnote{font-size:.82rem;color:#6b857e;margin:1rem 0 0;line-height:1.4}
.top3{margin:0 0 1.4rem}
.top3 h2{margin:0 0 .35rem;color:#0b3d2a;font-size:1.35rem}
.top3 .lead{margin:0 0 .85rem;color:#3d5c55;line-height:1.5}
.top3-list{display:grid;gap:.75rem;margin:0;padding:0;list-style:none;counter-reset:top3}
.top3-item{display:grid;grid-template-columns:auto 1fr;gap:.75rem;align-items:start;
background:#fff;border:1px solid #c5ddd5;border-radius:14px;padding:.95rem 1.05rem;
box-shadow:0 4px 18px rgba(11,61,42,.06)}
.top3-num{width:2rem;height:2rem;border-radius:50%;background:#0b3d2a;color:#fff;
font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.top3-item h3{margin:0 0 .3rem;color:#0b3d2a;font-size:1.05rem}
.top3-item p{margin:0;color:#334;font-size:.95rem;line-height:1.5}
.top3-step{margin:.45rem 0 0!important;color:#0d5c4d!important;font-weight:600}
</style>
"""

THEME_HINTS = [
    ('gall', 'Gallbladder & bile flow',
     'The scan marked extra load around bile flow. Heavy or fried meals often sit too long with this pattern. Smaller meals and bitter greens are a simple first step.'),
    ('bile', 'Gallbladder & bile flow',
     'Bile-flow patterns showed up. Fats can feel heavy. Go easy on large fatty meals while things settle.'),
    ('lymph', 'Lymph & drainage',
     'Drainage points were marked. Think congestion or slow recovery \u2014 walking, hydration, and daily movement are simple supports.'),
    ('kidney', 'Kidneys & fluid balance',
     'Kidney-related patterns were in the scan. Steady hydration through the day usually matters more than a large amount at night.'),
    ('liver', 'Liver & processing load',
     'Liver-related markers were active. Alcohol, ultra-processed snacks, and late heavy dinners add load.'),
    ('intestin', 'Digestion',
     'The gut showed extra signal. Simple meals, cooked vegetables, and less sugar usually help this pattern.'),
    ('digest', 'Digestion',
     'Digestion was part of the scan picture. Chew well and keep constant snacking down.'),
    ('stomach', 'Digestion',
     'Stomach load showed up. Large drinks with meals can add bloat for some people.'),
    ('candida', 'Yeast / sugar load',
     'A yeast-and-sugar pattern is in the scan. Cutting soda, juice, and dessert for a stretch is a practical experiment.'),
    ('colon', 'Lower gut',
     'The lower gut was flagged. Fiber from vegetables plus water is the first lever.'),
    ('immune', 'Immune load',
     'Immune markers were active. Sleep and a lower-sugar week are practical supports.'),
    ('thyroid', 'Thyroid & energy',
     'Thyroid-related signal appeared. A standard thyroid blood panel with your clinician is the usual next lab if you have not had one recently.'),
    ('adren', 'Stress reserve',
     'Stress-reserve markers were up. Earlier nights help more than extra caffeine.'),
    ('stress', 'Stress reserve',
     'Stress load is part of this scan. Keep evenings dim and meals earlier when you can.'),
    ('sleep', 'Sleep rhythm',
     'Sleep-related patterns showed up. A consistent bedtime and a darker room are the baseline supports.'),
    ('hormon', 'Hormonal rhythm',
     'Hormone-related markers were noted. This is a wellness pattern, not a hormone diagnosis.'),
    ('metabol', 'Energy & metabolism',
     'Metabolic energy patterns were active. Regular protein, walking after meals, and fewer ultra-processed snacks are simple supports.'),
]


def _first_name(client_name):
    name = (client_name or '').strip()
    if not name or '@' in name:
        return 'there'
    return escape(name.split()[0])


def theme_cards_html(raw_data, limit=6):
    """Short plain-English theme cards from scan text. Never a diagnosis."""
    text = (raw_data or '').lower()
    found, seen = [], set()
    for key, title, blurb in THEME_HINTS:
        if key in text and title not in seen:
            seen.add(title)
            found.append((title, blurb))
        if len(found) >= limit:
            break
    if not found:
        found = [(
            'How to read this report',
            'Start with Health Scores and the short themes. Open the lists only if you want the item names from the scan file.',
        )]
    cards = ''.join(
        f'<article class="wellness-theme-card"><h4>{escape(t)}</h4><p>{escape(b)}</p></article>'
        for t, b in found
    )
    return f'<div class="wellness-theme-grid">{cards}</div>'


SYSTEM_PLAIN = {
    'digestive': (
        'Digestion',
        'Your scan put extra weight on the gut \u2014 how food is broken down and how comfortable meals feel afterward.',
        'Start with simpler meals, chew well, and cut back on constant snacking for a week.',
    ),
    'liver_gallbladder': (
        'Liver and bile flow',
        'Processing and bile-flow patterns stood out. Large, fried, or very fatty meals often feel heavier with this picture.',
        'Keep dinners earlier and smaller, and go easy on fried food while you watch how you feel.',
    ),
    'immune': (
        'Immune load',
        'Immune-related markers were among the strongest signals. Think recovery load \u2014 sleep and sugar usually matter here.',
        'Protect sleep and skip soda, juice, and dessert for a short stretch to see if you feel clearer.',
    ),
    'nervous': (
        'Stress and nerves',
        'Nervous-system and stress-reserve patterns were high on the list. This is about load, not a diagnosis.',
        'Pick one earlier bedtime and keep caffeine to the morning for several days.',
    ),
    'hormones': (
        'Hormone rhythm',
        'Hormone-related markers showed up. This is a wellness pattern from the scan, not a lab hormone diagnosis.',
        'Keep meals and sleep on a steady schedule, and share questions about symptoms with your clinician.',
    ),
    'metabolism': (
        'Energy and metabolism',
        'Cellular-energy patterns were active. Days can feel flat when fuel and recovery are uneven.',
        'Add protein at breakfast and take a 10-minute walk after your largest meal.',
    ),
    'lymph': (
        'Drainage',
        'Lymph and drainage points were marked. Congestion or slow bounce-back is the everyday version of this theme.',
        'Walk daily and drink water through the day instead of a large amount at night.',
    ),
    'reproductive': (
        'Kidneys and fluid balance',
        'Kidney, bladder, or reproductive-pathway markers were part of the picture. Hydration timing often matters more than volume.',
        'Sip water evenly through the day and notice afternoon energy versus late-night fluids.',
    ),
    'cardiovascular': (
        'Circulation',
        'Heart and circulation themes were among the louder scan signals. Movement and sleep are the practical first levers.',
        'Take a daily walk and keep ultra-processed snacks down this week.',
    ),
    'respiratory': (
        'Breathing comfort',
        'Lung and airway patterns showed up. This is a wellness note from the scan, not a breathing-test result.',
        'Notice indoor air, and mention ongoing shortness of breath to a clinician.',
    ),
    'pancreas': (
        'Blood-sugar rhythm',
        'Pancreas and blood-sugar related markers were active. Swings after sweet drinks are a common everyday clue.',
        'Pair carbs with protein and skip sweet drinks for a week as a simple experiment.',
    ),
    'dermal': (
        'Skin and barrier',
        'Skin and barrier markers were part of the louder findings. Hydration and fewer packaged snacks are a gentle first step.',
        'Keep showers shorter and watch whether sugar-heavy days line up with flare-ups.',
    ),
    'muscles': (
        'Muscles and recovery',
        'Muscle and joint-related markers stood out. Recovery and minerals often sit behind this theme.',
        'Add a short daily stretch or walk, and avoid training to exhaustion this week.',
    ),
    'blood': (
        'Blood-quality signals',
        'Blood-related markers were noted. This is a scan pattern, not a laboratory blood panel.',
        'If you have not had recent bloodwork with a clinician, that is the usual next clinical step.',
    ),
    'thyroid': (
        'Thyroid and energy',
        'Thyroid-related signal appeared among the stronger themes.',
        'A standard thyroid blood panel with your clinician is the usual next lab if you have not had one recently.',
    ),
}


def _priorities_from_overview(raw_data):
    try:
        from scan_template import _find_sections, _parse_hormone_items, _extract_hormone_block, _parse_imbalance_cards
        from body_overview import build_body_overview
        text = raw_data or ''
        sections = _find_sections(text)
        hormones = _parse_hormone_items(_extract_hormone_block(text, sections))
        cards = (
            _parse_imbalance_cards(sections.get('metabolic', ''))
            + _parse_imbalance_cards(sections.get('sleep', ''))
            + _parse_imbalance_cards(sections.get('hormone_test', ''))
        )
        overview = build_body_overview(text, sections, cards, hormones)
    except Exception:
        return []
    ranked = [s for s in (overview or []) if s.get('markers')]
    ranked.sort(key=lambda s: (s.get('score', 100), -len(s.get('markers') or [])))
    out = []
    seen = set()
    for system in ranked:
        spec = SYSTEM_PLAIN.get(system.get('id'))
        if not spec:
            title = system.get('name') or 'Body system'
            spec = (
                title,
                'This system had more scan markers than the others, so it belongs near the top of your list.',
                'Read the matching section below and pick one small daily change to try for a week.',
            )
        title, why, step = spec
        if title in seen:
            continue
        seen.add(title)
        out.append((title, why, step))
        if len(out) >= 3:
            break
    return out


def _priorities_from_themes(raw_data):
    text = (raw_data or '').lower()
    found, seen = [], set()
    for key, title, blurb in THEME_HINTS:
        if key in text and title not in seen:
            seen.add(title)
            step = 'Try one small change from this theme for a week and notice how you feel.'
            found.append((title, blurb, step))
        if len(found) >= 3:
            break
    return found


def pick_top_priorities(raw_data, limit=3):
    items = _priorities_from_overview(raw_data)
    if len(items) < limit:
        have = {t for t, _, _ in items}
        for title, why, step in _priorities_from_themes(raw_data):
            if title in have:
                continue
            items.append((title, why, step))
            have.add(title)
            if len(items) >= limit:
                break
    if not items:
        items = [(
            'Read the Health Scores first',
            'This scan did not give a clear three-item ranking, so start with the overall score and the body-system bars.',
            'Open one system section that matches how you feel day to day.',
        )]
    return items[:limit]


def top_priorities_html(raw_data, client_name=None):
    """Numbered top-3 list in plain language. Wellness only \u2014 not a diagnosis."""
    items = pick_top_priorities(raw_data)
    first = _first_name(client_name)
    rows = []
    for idx, (title, why, step) in enumerate(items, start=1):
        rows.append(
            '<li class="top3-item">'
            f'<span class="top3-num" aria-hidden="true">{idx}</span>'
            '<div>'
            f'<h3>{escape(title)}</h3>'
            f'<p>{escape(why)}</p>'
            f'<p class="top3-step">Simple first step: {escape(step)}</p>'
            '</div></li>'
        )
    return (
        '<section class="top3" id="your-top-priorities" aria-label="Your top 3 priorities">'
        f'<h2>Your top 3 priorities</h2>'
        f'<p class="lead">{first}, start here. These are the three patterns that stood out most '
        'on this wellness scan, written in everyday language. They are not a diagnosis, '
        'not an allergy result, and not a treatment plan.</p>'
        f'<ol class="top3-list">{{"".join(rows)}</ol>'
        '</section>'
    )


def _banner_html(client_name=None):
    first = _first_name(client_name)
    return (
        f'<aside class="wellness-banner" aria-label="How to read this wellness report">'
        f'<h2>Your wellness report</h2>'
        f'<p>Hi {first}. This page is written in everyday language. Health Scores '
        f'(0\u2013100, higher is better) summarize how balanced each body system looked on this scan.</p>'
        f'<p><strong>Your top 3 priorities</strong> come first, in everyday language. '
        f'Long item lists from the scanner file are folded up so they do not dominate the page.</p>'
        f'<div class="wellness-pill-row">'
        f'<span class="wellness-pill">Informational only</span>'
        f'<span class="wellness-pill">Not a diagnosis</span>'
        f'<span class="wellness-pill">Not an allergy test</span>'
        f'<span class="wellness-pill">Not a substitute for a clinician</span>'
        f'</div></aside>'
    )


def collapse_raw_lists(html):
    """Fold bulky scanner lists so summaries stay on top."""
    if not html or 'wellness-raw-toggle' in html:
        return html

    def wrap_columns(match):
        lead, columns, tail = match.group(1), match.group(2), match.group(3)
        return (
            f'{lead}<details class="wellness-raw-toggle">'
            f'<summary>Show detailed item lists</summary>{columns}</details>{tail}'
        )

    html = re.sub(
        r'(<p class="scan-lead">[\s\S]*?</p>\s*)'
        r'(<div class="scan-columns">[\s\S]*?</div>)'
        r'(\s*</section>)',
        wrap_columns,
        html,
        flags=re.I,
    )

    def wrap_findings(match):
        return (
            f'{match.group(1)}<details class="wellness-raw-toggle">'
            f'<summary>Show marker details</summary>'
            f'{match.group(2)}</details>{match.group(3)}'
        )

    html = re.sub(
        r'(<h3>[^<]+</h3>\s*)'
        r'(<div class="findings-grid">[\s\S]*?</div>)'
        r'(\s*</section>)',
        wrap_findings,
        html,
        flags=re.I,
    )
    return html


def ensure_wellness_disclaimer(html):
    if not html:
        return html
    if 'not intended to diagnose' in html.lower() or 'not a medical diagnosis' in html.lower():
        return html
    note = (
        '<p class="wellness-footnote">This report is educational wellness content. '
        'It is not a medical diagnosis, treatment plan, allergy test, DNA test, or HTMA, '
        'and it does not replace care from a licensed clinician.</p>'
    )
    if '</article>' in html:
        return html.replace('</article>', note + '</article>', 1)
    return html + note


def wrap_wellness_report(html, client_name=None, title=None, raw_data=None):
    """Idempotent chrome around any generated report HTML."""
    html = html or ''
    if len(html.strip()) < 40:
        return html
    html = collapse_raw_lists(html)
    html = ensure_wellness_disclaimer(html)
    priorities = top_priorities_html(raw_data, client_name=client_name)
    if WELLNESS_MARKER in html:
        if 'id="your-top-priorities"' not in html:
            html = re.sub(
                r'(</aside>\s*)',
                r'\1' + priorities,
                html,
                count=1,
            )
            if 'id="your-top-priorities"' not in html:
                html = html.replace(
                    f'<div class="wellness-report" {WELLNESS_MARKER}>',
                    f'<div class="wellness-report" {WELLNESS_MARKER}>{priorities}',
                    1,
                )
        if '.top3{' not in html and WELLNESS_STYLES not in html:
            html = html.replace('</style>', WELLNESS_STYLES.replace('<style>', '', 1), 1)
        elif '.top3{' not in html:
            extra = WELLNESS_STYLES.replace('<style>', '').replace('</style>', '')
            html = html.replace('</style>', extra + '</style>', 1)
        return html
    themes = theme_cards_html(raw_data) if raw_data else ''
    return (
        f'<div class="wellness-report" {WELLNESS_MARKER}>'
        f'{WELLNESS_STYLES}'
        f'{_banner_html(client_name)}'
        f'{priorities}'
        f'{themes}'
        f'{html}'
        f'</div>'
    )
