"""Reusable wellness-only report chrome.

Wraps generated scan HTML so clients see plain English first:
priority themes, Health Scores, then collapsible raw lists.
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
details.wellness-raw-toggle>summary:after{content:" ▾";font-weight:400;color:#6b857e}
details.wellness-raw-toggle[open]>summary:after{content:" ▴"}
.raw-count{display:inline-block;background:#e8f5f1;border-radius:999px;padding:.05rem .5rem;
font-size:.78rem;margin-left:.35rem;color:#0d5c4d}
.wellness-footnote{font-size:.82rem;color:#6b857e;margin:1rem 0 0;line-height:1.4}
</style>
"""

THEME_HINTS = [
    ('gall', 'Gallbladder & bile flow',
     'The scan marked extra load around bile flow. Heavy or fried meals often sit too long with this pattern. Smaller meals and bitter greens are a simple first step.'),
    ('bile', 'Gallbladder & bile flow',
     'Bile-flow patterns showed up. Fats can feel heavy. Go easy on large fatty meals while things settle.'),
    ('lymph', 'Lymph & drainage',
     'Drainage points were marked. Think congestion or slow recovery — walking, hydration, and daily movement are simple supports.'),
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


def _banner_html(client_name=None):
    first = _first_name(client_name)
    return (
        f'<aside class="wellness-banner" aria-label="How to read this wellness report">'
        f'<h2>Your wellness report</h2>'
        f'<p>Hi {first}. This page is written in everyday language. Health Scores '
        f'(0–100, higher is better) summarize how balanced each body system looked on this scan.</p>'
        f'<p>Priority themes come first. Long item lists from the scanner file are folded up so they '
        f'do not dominate the page. Open a section only if you want the raw names.</p>'
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
    if WELLNESS_MARKER in html:
        return html
    themes = theme_cards_html(raw_data) if raw_data else ''
    return (
        f'<div class="wellness-report" {WELLNESS_MARKER}>'
        f'{WELLNESS_STYLES}'
        f'{_banner_html(client_name)}'
        f'{themes}'
        f'{html}'
        f'</div>'
    )
