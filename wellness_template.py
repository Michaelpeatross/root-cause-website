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
.raw-count{display:inline-block;background:#e8f5f1;border-radius:999px;padding:.05rem .5rem;
font-size:.78rem;margin-left:.35rem;color:#0d5c4d}
.wellness-footnote{font-size:.82rem;color:#6b857e;margin:1rem 0 0;line-height:1.4}
.top3{margin:0 0 1.4rem}
.top3 h2{margin:0 0 .35rem;color:#0b3d2a;font-size:1.35rem}
.top3 .lead{margin:0 0 .85rem;color:#3d5c55;line-height:1.5}
.top3-list{display:grid;gap:.75rem;margin:0;padding:0;list-style:none}
.top3-item{display:grid;grid-template-columns:auto 1fr;gap:.75rem;align-items:start;
background:#fff;border:1px solid #c5ddd5;border-radius:14px;padding:.95rem 1.05rem}
.top3-num{width:2rem;height:2rem;border-radius:50%;background:#0b3d2a;color:#fff;
font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.top3-item h3{margin:0;color:#0b3d2a;font-size:1.05rem}
.top3-item p{margin:0;color:#334;font-size:.95rem;line-height:1.5}
.top3-step{margin:.45rem 0 0!important;color:#0d5c4d!important;font-weight:600}
.top3-head{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin:0 0 .3rem}
.info-badge{display:inline-flex;align-items:center;border-radius:999px;padding:.12rem .55rem;
font-size:.72rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase;
border:1px solid transparent;line-height:1.2}
.info-badge.high{background:#fde8e8;color:#9b1c1c;border-color:#f5c2c2}
.info-badge.medium{background:#fff4d6;color:#92400e;border-color:#f3d19a}
.info-badge.low{background:#e7f7ee;color:#0f6b3d;border-color:#b7e4c7}
.info-badge-legend{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;margin:.55rem 0 .85rem}
.info-badge-legend .hint{font-size:.78rem;color:#6b857e}
</style>
"""

THEME_HINTS = [
    ('gall', 'Gallbladder and bile flow', 'The scan marked extra load around bile flow. Smaller meals and bitter greens are a simple first step.'),
    ('bile', 'Gallbladder and bile flow', 'Bile-flow patterns showed up. Go easy on large fatty meals while things settle.'),
    ('lymph', 'Lymph and drainage', 'Drainage points were marked. Walking, hydration, and daily movement are simple supports.'),
    ('kidney', 'Kidneys and fluid balance', 'Kidney-related patterns were in the scan. Steady hydration through the day usually matters more than a large amount at night.'),
    ('liver', 'Liver and processing load', 'Liver-related markers were active. Alcohol, ultra-processed snacks, and late heavy dinners add load.'),
    ('intestin', 'Digestion', 'The gut showed extra signal. Simple meals, cooked vegetables, and less sugar usually help this pattern.'),
    ('digest', 'Digestion', 'Digestion was part of the scan picture. Chew well and keep constant snacking down.'),
    ('stomach', 'Digestion', 'Stomach load showed up. Large drinks with meals can add bloat for some people.'),
    ('candida', 'Yeast / sugar load', 'A yeast-and-sugar pattern is in the scan. Cutting soda, juice, and dessert for a stretch is a practical experiment.'),
    ('colon', 'Lower gut', 'The lower gut was flagged. Fiber from vegetables plus water is the first lever.'),
    ('immune', 'Immune load', 'Immune markers were active. Sleep and a lower-sugar week are practical supports.'),
    ('thyroid', 'Thyroid and energy', 'Thyroid-related signal appeared. A standard thyroid blood panel with your clinician is the usual next lab if you have not had one recently.'),
    ('adren', 'Stress reserve', 'Stress-reserve markers were up. Earlier nights help more than extra caffeine.'),
    ('stress', 'Stress reserve', 'Stress load is part of this scan. Keep evenings dim and meals earlier when you can.'),
    ('sleep', 'Sleep rhythm', 'Sleep-related patterns showed up. A consistent bedtime and a darker room are the baseline supports.'),
    ('hormon', 'Hormonal rhythm', 'Hormone-related markers were noted. This is a wellness pattern, not a hormone diagnosis.'),
    ('metabol', 'Energy and metabolism', 'Metabolic energy patterns were active. Regular protein and walking after meals are simple supports.'),
]

SYSTEM_PLAIN = {
    'digestive': ('Digestion', 'Your scan put extra weight on the gut - how food is broken down and how comfortable meals feel afterward.', 'Start with simpler meals, chew well, and cut back on constant snacking for a week.'),
    'liver_gallbladder': ('Liver and bile flow', 'Processing and bile-flow patterns stood out. Large, fried, or very fatty meals often feel heavier with this picture.', 'Keep dinners earlier and smaller, and go easy on fried food while you watch how you feel.'),
    'immune': ('Immune load', 'Immune-related markers were among the strongest signals. Think recovery load - sleep and sugar usually matter here.', 'Protect sleep and skip soda, juice, and dessert for a short stretch to see if you feel clearer.'),
    'nervous': ('Stress and nerves', 'Nervous-system and stress-reserve patterns were high on the list. This is about load, not a diagnosis.', 'Pick one earlier bedtime and keep caffeine to the morning for several days.'),
    'hormones': ('Hormone rhythm', 'Hormone-related markers showed up. This is a wellness pattern from the scan, not a lab hormone diagnosis.', 'Keep meals and sleep on a steady schedule, and share questions about symptoms with your clinician.'),
    'metabolism': ('Energy and metabolism', 'Cellular-energy patterns were active. Days can feel flat when fuel and recovery are uneven.', 'Add protein at breakfast and take a 10-minute walk after your largest meal.'),
    'lymph': ('Drainage', 'Lymph and drainage points were marked. Congestion or slow bounce-back is the everyday version of this theme.', 'Walk daily and drink water through the day instead of a large amount at night.'),
    'reproductive': ('Kidneys and fluid balance', 'Kidney, bladder, or reproductive-pathway markers were part of the picture. Hydration timing often matters more than volume.', 'Sip water evenly through the day and notice afternoon energy versus late-night fluids.'),
    'cardiovascular': ('Circulation', 'Heart and circulation themes were among the louder scan signals. Movement and sleep are the practical first levers.', 'Take a daily walk and keep ultra-processed snacks down this week.'),
    'respiratory': ('Breathing comfort', 'Lung and airway patterns showed up. This is a wellness note from the scan, not a breathing-test result.', 'Notice indoor air, and mention ongoing shortness of breath to a clinician.'),
    'pancreas': ('Blood-sugar rhythm', 'Pancreas and blood-sugar related markers were active. Swings after sweet drinks are a common everyday clue.', 'Pair carbs with protein and skip sweet drinks for a week as a simple experiment.'),
    'dermal': ('Skin and barrier', 'Skin and barrier markers were part of the louder findings. Hydration and fewer packaged snacks are a gentle first step.', 'Keep showers shorter and watch whether sugar-heavy days line up with flare-ups.'),
    'muscles': ('Muscles and recovery', 'Muscle and joint-related markers stood out. Recovery and minerals often sit behind this theme.', 'Add a short daily stretch or walk, and avoid training to exhaustion this week.'),
    'blood': ('Blood-quality signals', 'Blood-related markers were noted. This is a scan pattern, not a laboratory blood panel.', 'If you have not had recent bloodwork with a clinician, that is the usual next clinical step.'),
}

PRIORITY_STEPS = {
    'Gallbladder and bile flow': 'Smaller meals, and a bitter green such as arugula with lunch, for one week.',
    'Lymph and drainage': 'A daily walk, and water spread through the day instead of a large glass at night.',
    'Kidneys and fluid balance': 'Sip water evenly through the day and notice afternoon energy versus late-night fluids.',
    'Liver and processing load': 'Skip alcohol and late heavy dinners for a week and see how mornings feel.',
    'Digestion': 'Simpler meals, chew well, and cut constant snacking for a week.',
    'Yeast / sugar load': 'No soda, juice, or dessert for a week as a short experiment.',
    'Lower gut': 'Vegetables plus water each day, and notice how the lower gut feels.',
    'Immune load': 'Protect sleep and skip sweet drinks for a week.',
    'Thyroid and energy': 'Ask your clinician whether a standard thyroid panel is due.',
    'Stress reserve': 'An earlier bedtime and caffeine only in the morning for several days.',
    'Sleep rhythm': 'A consistent bedtime and a darker room this week.',
    'Hormonal rhythm': 'Steady meal and sleep times, then share symptoms with your clinician.',
    'Energy and metabolism': 'Protein at breakfast and a 10-minute walk after the largest meal.',
}

PRACTITIONER_QUESTIONS = {
    'Gallbladder and bile flow': 'Fatty meals sit heavy. Is a standard liver panel (ALT, AST, GGT, bilirubin) worth ordering, separate from this wellness scan?',
    'Lymph and drainage': 'I feel puffy or slow to recover. What symptoms should make me come in, versus walking and drinking more water?',
    'Kidneys and fluid balance': 'Fluid balance showed up as a scan pattern. Should I have a basic kidney panel (creatinine, eGFR) if I have not had one this year?',
    'Liver and processing load': 'Which liver labs, if any, match late heavy meals or alcohol, separate from this wellness scan?',
    'Digestion': 'Meals feel heavy. What symptoms would make a stool test or H. pylori check reasonable, versus a simpler-meals trial first?',
    'Yeast / sugar load': 'If I cut sweet drinks for a few weeks, which symptoms should I report back to you?',
    'Stress reserve': 'Sleep and caffeine seem to drive how I feel. What should I track before we talk about more testing?',
    'Thyroid and energy': 'Is a standard thyroid panel due, separate from this wellness scan?',
}


def _step_for(title):
    try:
        from organ_ratings import ORGANS
        for name, _keys, _why, step, _question in ORGANS:
            if name == title:
                return step
    except Exception:
        pass
    return PRIORITY_STEPS.get(title) or 'Try the suggestion in this theme for one week and notice how you feel.'


def practitioner_questions_for(titles):
    organ_q = {}
    try:
        from organ_ratings import ORGANS
        organ_q = {name: question for name, _k, _w, _s, question in ORGANS}
    except Exception:
        organ_q = {}
    items, seen = [], set()
    for title in titles or []:
        q = organ_q.get(title) or PRACTITIONER_QUESTIONS.get(title) or (
            'What should I tell my clinician about %s, without treating this scan as a diagnosis?' % title
        )
        if q not in seen:
            seen.add(q)
            items.append(q)
    if not items:
        items.append('Which of these wellness patterns is worth a standard lab check first, separate from this scan?')
    return items[:3]


PRIORITY_BADGES = (('high', 'High'), ('medium', 'Medium'), ('low', 'Low'))


def _first_name(client_name):
    name = (client_name or '').strip()
    if not name or '@' in name:
        return 'there'
    return escape(name.split()[0])


def info_badge_html(level):
    level = (level or 'medium').lower()
    if level not in ('high', 'medium', 'low'):
        level = 'medium'
    return '<span class="info-badge ' + level + '" title="Informational emphasis only - not a diagnosis">' + level.capitalize() + '</span>'


def theme_cards_html(raw_data, limit=6):
    text = (raw_data or '').lower()
    found, seen = [], set()
    for key, title, blurb in THEME_HINTS:
        if key in text and title not in seen:
            seen.add(title)
            found.append((title, blurb))
        if len(found) >= limit:
            break
    if not found:
        found = [('How to read this report', 'Start with Health Scores and the short themes. Open the lists only if you want the item names from the scan file.')]
    cards = ''.join('<article class="wellness-theme-card"><h4>' + escape(t) + '</h4><p>' + escape(b) + '</p></article>' for t, b in found)
    return '<div class="wellness-theme-grid">' + cards + '</div>'


def _priorities_from_overview(raw_data):
    try:
        from scan_template import _find_sections, _parse_hormone_items, _extract_hormone_block, _parse_imbalance_cards
        from body_overview import build_body_overview
        text = raw_data or ''
        sections = _find_sections(text)
        hormones = _parse_hormone_items(_extract_hormone_block(text, sections))
        cards = _parse_imbalance_cards(sections.get('metabolic', '')) + _parse_imbalance_cards(sections.get('sleep', '')) + _parse_imbalance_cards(sections.get('hormone_test', ''))
        overview = build_body_overview(text, sections, cards, hormones)
    except Exception:
        return []
    ranked = [s for s in (overview or []) if s.get('markers')]
    ranked.sort(key=lambda s: (s.get('score', 100), -len(s.get('markers') or [])))
    out, seen = [], set()
    for system in ranked:
        spec = SYSTEM_PLAIN.get(system.get('id'))
        if not spec:
            spec = (system.get('name') or 'Body system', 'This system had more scan markers than the others, so it belongs near the top of your list.', 'Read the matching section below and pick one small daily change to try for a week.')
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
            found.append((title, blurb, _step_for(title)))
        if len(found) >= 3:
            break
    return found


def pick_top_priorities(raw_data, limit=3):
    items = []
    try:
        from organ_ratings import priority_items
        items = priority_items(raw_data, limit=limit)
    except Exception:
        items = []
    if len(items) < limit:
        have = {t for t, _, _ in items}
        for title, why, step in _priorities_from_overview(raw_data) + _priorities_from_themes(raw_data):
            if title in have:
                continue
            items.append((title, why, step))
            have.add(title)
            if len(items) >= limit:
                break
    if not items:
        items = [('Read the organ ratings first', 'This scan did not give a clear three-item ranking, so start with the organ table.', 'Notice which organ age sits furthest from calendar age.')]
    return items[:limit]


def top_priorities_html(raw_data, client_name=None):
    items = pick_top_priorities(raw_data)
    bands = {}
    try:
        from organ_ratings import rate_organs
        bands = {row['title']: row['band'] for row in rate_organs(raw_data)}
    except Exception:
        bands = {}
    band_level = {'Higher load': 'high', 'Moderate load': 'medium', 'Mild load': 'low', 'Steady': 'low'}
    first = _first_name(client_name)
    rows = []
    for idx, (title, why, step) in enumerate(items, start=1):
        level = band_level.get(bands.get(title)) or PRIORITY_BADGES[min(idx - 1, 2)][0]
        rows.append(
            '<li class="top3-item"><span class="top3-num" aria-hidden="true">' + str(idx) + '</span><div>'
            '<div class="top3-head"><h3>' + escape(title) + '</h3>' + info_badge_html(level) + '</div>'
            '<p>' + escape(why) + '</p>'
            '<p class="top3-step">Simple first step: ' + escape(step) + '</p></div></li>'
        )
    legend = (
        '<div class="info-badge-legend">' + info_badge_html('high') + info_badge_html('medium') + info_badge_html('low') +
        '<span class="hint">Informational emphasis on this scan - not a diagnosis or lab grade.</span></div>'
    )
    return (
        '<section class="top3" id="your-top-priorities" aria-label="Your top 3 priorities">'
        '<h2>Your top 3 priorities</h2>'
        '<p class="lead">' + first + ', these are the three organs that stood out most on the list above. '
        'Color badges match that rating. They are not a diagnosis, not an allergy result, and not a treatment plan.</p>'
        + legend +
        '<ol class="top3-list">' + ''.join(rows) + '</ol></section>'
    )


def _banner_html(client_name=None):
    first = _first_name(client_name)
    return (
        '<aside class="wellness-banner" aria-label="How to read this wellness report">'
        '<h2>Your wellness report</h2>'
        '<p>Hi ' + first + '. Findings come first: how each organ looked, then what to do about it.</p>'
        '<p class="wellness-disclaimer-line">Informational only. This is not a diagnosis, not an allergy test, and not a substitute for a clinician.</p>'
        '</aside>'
    )


def collapse_raw_lists(html):
    if not html or 'wellness-raw-toggle' in html:
        return html
    def wrap_columns(match):
        return match.group(1) + '<details class="wellness-raw-toggle"><summary>Show detailed item lists</summary>' + match.group(2) + '</details>' + match.group(3)
    html = re.sub(r'(<p class="scan-lead">[\s\S]*?</p>\s*)(<div class="scan-columns">[\s\S]*?</div>)(\s*</section>)', wrap_columns, html, flags=re.I)
    def wrap_findings(match):
        return match.group(1) + '<details class="wellness-raw-toggle"><summary>Show marker details</summary>' + match.group(2) + '</details>' + match.group(3)
    html = re.sub(r'(<h3>[^<]+</h3>\s*)(<div class="findings-grid">[\s\S]*?</div>)(\s*</section>)', wrap_findings, html, flags=re.I)
    return html


def ensure_wellness_disclaimer(html):
    if not html:
        return html
    if 'not intended to diagnose' in html.lower() or 'not a medical diagnosis' in html.lower():
        return html
    note = '<p class="wellness-footnote">This report is educational wellness content. It is not a medical diagnosis, treatment plan, allergy test, DNA test, or HTMA, and it does not replace care from a licensed clinician.</p>'
    if '</article>' in html:
        return html.replace('</article>', note + '</article>', 1)
    return html + note


def inject_emphasis_badges(html):
    if not html:
        return html
    def from_score(score):
        try:
            score = int(score)
        except (TypeError, ValueError):
            return 'medium'
        if score <= 50:
            return 'high'
        if score <= 70:
            return 'medium'
        return 'low'
    def add_after_pill(match):
        whole, score = match.group(0), match.group(1)
        return whole + info_badge_html(from_score(score))
    if 'class="health-score-pill' in html:
        html = re.sub(r'<span class="health-score-pill[^"]*">\s*(\d+)\s*</span>(?!\s*<span class="info-badge")', add_after_pill, html)
    if '.info-badge{' not in html and '</style>' in html:
        extra = WELLNESS_STYLES.replace('<style>', '').replace('</style>', '')
        html = html.replace('</style>', extra + '</style>', 1)
    return html


def wrap_wellness_report(html, client_name=None, title=None, raw_data=None):
    html = html or ''
    if len(html.strip()) < 40:
        return html
    html = collapse_raw_lists(html)
    html = ensure_wellness_disclaimer(html)
    priorities = top_priorities_html(raw_data, client_name=client_name)
    if WELLNESS_MARKER in html:
        if 'id="your-top-priorities"' not in html:
            html = re.sub(r'(</aside>\s*)', r'\1' + priorities, html, count=1)
            if 'id="your-top-priorities"' not in html:
                html = html.replace('<div class="wellness-report" ' + WELLNESS_MARKER + '>', '<div class="wellness-report" ' + WELLNESS_MARKER + '>' + priorities, 1)
        if '.info-badge{' not in html:
            extra = WELLNESS_STYLES.replace('<style>', '').replace('</style>', '')
            if '</style>' in html:
                html = html.replace('</style>', extra + '</style>', 1)
            else:
                html = WELLNESS_STYLES + html
        return inject_emphasis_badges(html)
    themes = theme_cards_html(raw_data) if raw_data else ''
    wrapped = '<div class="wellness-report" ' + WELLNESS_MARKER + '>' + WELLNESS_STYLES + _banner_html(client_name) + priorities + themes + html + '</div>'
    return inject_emphasis_badges(wrapped)


def _priority_titles(html):
    titles = re.findall(r'<div class="top3-head">\s*<h3>(.*?)</h3>', html or '', flags=re.I | re.S)
    clean = []
    for title in titles:
        text = re.sub(r'<[^>]+>', '', title).strip()
        if text and text not in clean:
            clean.append(text)
    return clean[:3]


def _rewrite_priority_steps(html):
    def repl(match):
        title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        step = _step_for(title)
        return match.group(0).split('<p class="top3-step">')[0] + '<p class="top3-step">Simple first step: ' + escape(step) + '</p>'
    return re.sub(
        r'<div class="top3-head">\s*<h3>(.*?)</h3>[\s\S]*?<p class="top3-step">[\s\S]*?</p>',
        repl,
        html or '',
        flags=re.I,
    )


def _rewrite_questions(html):
    if 'rc-q-list' not in (html or ''):
        return html
    questions = practitioner_questions_for(_priority_titles(html))
    lis = ''.join(
        '<li><h3>Question %s</h3><p>%s</p></li>' % (i, escape(q))
        for i, q in enumerate(questions, start=1)
    )
    return re.sub(r'<ol class="rc-q-list">[\s\S]*?</ol>', '<ol class="rc-q-list">' + lis + '</ol>', html, count=1, flags=re.I)


def _pull_top3_out_of_glossary(html):
    """Older pages nested the priorities section inside an unclosed glossary."""
    start = html.find('<details class="glossary-panel"')
    top = html.find('<section class="top3" id="your-top-priorities"')
    if start == -1 or top == -1 or top < start:
        return html
    between = html[start:top]
    if '</dl>' in between:
        return html
    section = re.search(
        r'<section class="top3" id="your-top-priorities"[\s\S]*?</section>',
        html[top:],
    )
    if not section:
        return html
    return html[:start] + section.group(0) + html[top + section.end():]


def clean_client_report(html):
    """Client page and PDF: plain language only. No raw scanner names."""
    if not html:
        return html
    html = _pull_top3_out_of_glossary(html)
    html = re.sub(r'<details[^>]*(?:id="report-glossary"|glossary-panel)[\s\S]*?</dl>\s*</details>', '', html, flags=re.I)
    html = re.sub(r'<dl class="glossary-list"[\s\S]*?</dl>', '', html, flags=re.I)
    html = re.sub(r'<div class="glossary-item">[\s\S]*?</div>', '', html, flags=re.I)
    html = re.sub(
        r'<details class="jargon"><summary class="jargon-term">(.*?)</summary>[\s\S]*?</details>',
        r'\1',
        html,
        flags=re.I,
    )
    html = re.sub(
        r'<p><strong>Your top 3 priorities</strong> come first[\s\S]*?</p>\s*',
        '',
        html,
        count=1,
    )
    html = re.sub(
        r'<div class="wellness-pill-row">[\s\S]*?</div>',
        '<p class="wellness-disclaimer-line">Informational only. This is not a diagnosis, not an allergy test, and not a substitute for a clinician.</p>',
        html,
        count=1,
    )
    html = re.sub(r'<details class="wellness-raw-toggle">[\s\S]*?</details>', '', html, flags=re.I)
    html = re.sub(
        r'<section class="report-section">\s*<h3>[^<]*</h3>\s*(?:<div class="findings-grid">[\s\S]*?</div>\s*)?</section>',
        '',
        html,
        flags=re.I,
    )
    html = re.sub(
        r'<div class="finding-row">\s*<div class="finding-label">[\s\S]*?</div>\s*<div class="finding-meta">[\s\S]*?</div>\s*</div>',
        '',
        html,
        flags=re.I,
    )
    html = re.sub(r'<div class="findings-grid">[\s\S]*?</div>', '', html, flags=re.I)
    html = re.sub(
        r'<ul class="top-findings">[\s\S]*?</ul>',
        '<p class="rec-note">Scanner item names and machine codes stay with your practitioner. The organ chart above is the finding. The plan comes after.</p>',
        html,
        count=1,
        flags=re.I,
    )
    html = re.sub(
        r'Analysis identified <strong>\d+</strong> resonant markers[\s\S]*?requiring attention\.',
        'This page is a plain-language wellness summary. It is not a list of machine codes and it is not a diagnosis.',
        html,
        count=1,
    )
    html = html.replace(
        'Long item lists from the scanner file are folded up.',
        'Scanner item names stay with your practitioner.',
    )
    html = re.sub(r'/?\s*\d{3,5}\s+\d{1,2}/\d{1,2}/\d{2,4}\s*\d*', '', html)
    html = _rewrite_priority_steps(html)
    html = _rewrite_questions(html)
    return html


def _kept_age(html, calendar_age=None, biometric_age=None):
    if calendar_age is None:
        match = re.search(r'Calendar age:</strong>\s*(\d+)', html or '') or re.search(
            r'class="age-cal"[\s\S]{0,180}?class="age-num">\s*(\d+)', html or ''
        )
        if match:
            calendar_age = int(match.group(1))
    if biometric_age is None:
        match = re.search(r'Biometric age:</strong>\s*(\d+)', html or '') or re.search(
            r'class="age-bio"[\s\S]{0,180}?class="age-num">\s*(\d+)', html or ''
        )
        if match:
            biometric_age = int(match.group(1))
    return calendar_age, biometric_age


def _age_section(calendar_age, biometric_age, client_name):
    first = escape(((client_name or 'Client').split() or ['there'])[0])
    if not calendar_age or not biometric_age:
        return ''
    delta = int(biometric_age) - int(calendar_age)
    if delta > 5:
        biometric_age = int(calendar_age) + 5
        delta = 5
    if delta > 0:
        diff = '%s years older than calendar age' % delta
        summary = 'Scan patterns are reading older than calendar age.'
    elif delta < 0:
        diff = '%s years younger than calendar age' % abs(delta)
        summary = 'Scan patterns are reading younger than calendar age.'
    else:
        diff = 'matched to calendar age'
        summary = 'Scan patterns are close to calendar age.'
    return (
        '<section class="report-section biometric-age-block" id="biometric-age">'
        '<h3>Whole-person age</h3>'
        '<table class="age-compare" width="100%" cellpadding="8" cellspacing="6"><tr>'
        '<td width="50%" class="age-cal" bgcolor="#0b3d2a"><span class="age-label">Calendar age</span> '
        '<span class="age-num">' + str(int(calendar_age)) + '</span></td>'
        '<td width="50%" class="age-bio" bgcolor="#9b3a3a"><span class="age-label">Scan age</span> '
        '<span class="age-num">' + str(int(biometric_age)) + '</span></td>'
        '</tr></table>'
        '<p><strong>Difference:</strong> ' + diff + '</p>'
        '<p>' + summary + ' This is a bioenergetic wellness estimate, not a clinical aging test such as PhenoAge or DNA methylation.</p>'
        '<p class="rec-note">' + first + ', raw scanner percentages stay off this report.</p></section>'
    )


def _cut_balanced_div(html, start_token):
    start = html.find(start_token)
    if start < 0:
        return html
    i = start + len(start_token)
    depth = 1
    while i < len(html) and depth:
        open_at = html.find('<div', i)
        close_at = html.find('</div>', i)
        if close_at < 0:
            return html[:start]
        if open_at != -1 and open_at < close_at:
            depth += 1
            i = open_at + 4
        else:
            depth -= 1
            i = close_at + 6
    return html[:start] + html[i:]


def _drop_old_findings(html):
    """Remove current findings, including leftovers from an older short match."""
    token = '<div id="scan-findings">'
    for _ in range(12):
        if token not in html:
            break
        html = _cut_balanced_div(html, token)
    banner = html.find('<aside class="wellness-banner"')
    for _ in range(12):
        starts = []
        for needle in ('<div class="age-num">', '<div class="age-label">', '<h2>What this scan found</h2>', '<h3>Major organs</h3>', '<table class="organ-chart"'):
            at = html.find(needle)
            if at != -1 and (banner == -1 or at < banner):
                starts.append(at)
        if not starts:
            break
        start = min(starts)
        end = banner if banner != -1 and banner > start else html.find('<section class="top3"', start)
        if end == -1 or end <= start:
            break
        html = html[:start] + html[end:]
        banner = html.find('<aside class="wellness-banner"')
    return html


def place_findings_first(html, raw_data, client_name='Client', calendar_age=None, biometric_age=None, previous_scans=None, health_html=''):
    """Findings and organ ratings first. Teas, labs, and supplements after."""
    html = html or ''
    calendar_age, biometric_age = _kept_age(html, calendar_age, biometric_age)
    if calendar_age and biometric_age is not None:
        from biometric_age import cap_to_calendar
        biometric_age = cap_to_calendar(calendar_age, biometric_age)
    if not calendar_age and raw_data:
        try:
            from biometric_age import extract_calendar_age
            calendar_age = extract_calendar_age(raw_data)
        except Exception:
            pass
    html = re.sub(r'<div class="wellness-theme-grid">[\s\S]*?</div>', '', html, count=1)
    html = _drop_old_findings(html)
    html = re.sub(r'<section class="report-section biometric-age-block"[\s\S]*?</section>', '', html, count=1)
    try:
        from organ_ratings import organ_board_html, toxin_board_html, food_board_html
        board = organ_board_html(
            raw_data,
            calendar_age=calendar_age,
            biometric_age=biometric_age,
            client_name=client_name,
            previous_scans=previous_scans,
        )
        board += toxin_board_html(raw_data, client_name=client_name)
        board += food_board_html(raw_data, client_name=client_name)
    except Exception:
        board = ''
    first = escape(((client_name or 'Client').split() or ['there'])[0])
    findings = (
        '<div id="scan-findings"><style>'
        '.organ-board,.organ-chart{width:100%;border-collapse:collapse;margin:.5rem 0 1rem}'
        '.organ-board th,.organ-board td,.organ-chart th,.organ-chart td{border-bottom:1px solid #dceee8;padding:.45rem .4rem;text-align:left;vertical-align:middle}'
        '.organ-board th,.organ-chart th{color:#0b3d2a;font-size:.82rem}'
        '.rating-bar{width:100%;border-collapse:collapse;height:18px}'
        '.rating-bar td{border:0;padding:2px 4px;color:#fff;font-size:.78rem;font-weight:700}'
        '.bar-high{background:#c2413a;color:#fff}.bar-mod{background:#d97706;color:#fff}'
        '.bar-mild{background:#0f766e;color:#fff}.bar-ok{background:#1f8a5b;color:#fff}'
        '.bar-rest{background:#e7f0ec;color:transparent}'
        '.swatch{display:inline-block;padding:.1rem .45rem;border-radius:999px;margin-right:.35rem;font-size:.75rem}'
        '.chg-better{color:#0f6b3d;font-weight:700}.chg-worse{color:#9b1c1c;font-weight:700}.chg-same{color:#92400e}'
        '.age-compare td{border-radius:10px;padding:.7rem .8rem}'
        '.age-cal{background:#0b3d2a;color:#fff}.age-bio{background:#9b3a3a;color:#fff}'
        '.age-label{font-size:.75rem;letter-spacing:.04em;text-transform:uppercase}'
        '.age-num{font-size:1.8rem;font-weight:800;line-height:1.1}'
        '.toxin-chip{background:#7c2d12;color:#fff;font-weight:700;border-radius:999px;padding:.35rem .7rem}'
        '.food-chip{background:#166534;color:#fff;font-weight:700;border-radius:999px;padding:.35rem .7rem}'
        '.eat-chip{background:#1e40af;color:#fff;font-weight:700;border-radius:999px;padding:.35rem .7rem}'
        '</style>'
        '<h2>What this scan found</h2>'
        '<p>' + first + ', findings come first. What to do about them is further down.</p>'
        + _age_section(calendar_age, biometric_age, client_name)
        + board
        + (health_html or '')
        + '</div>'
    )
    new_top = top_priorities_html(raw_data, client_name=client_name)
    if 'id="your-top-priorities"' in html:
        html = re.sub(
            r'<section class="top3" id="your-top-priorities"[\s\S]*?</section>',
            new_top,
            html,
            count=1,
        )
    plan = ''
    match = re.search(r'<div class="client-wellness-plan"[\s\S]*?</div>', html)
    if match:
        plan = match.group(0).replace('Your Wellness Plan', 'What to do next', 1)
        html = html[:match.start()] + html[match.end():]
    marker = 'id="wellness-report-chrome"'
    if marker in html:
        idx = html.find(marker)
        gt = html.find('>', idx)
        rest = html[gt + 1:]
        prefix = html[:gt + 1]
        if rest.lstrip().startswith('<style>'):
            endstyle = rest.find('</style>')
            if endstyle != -1:
                html = prefix + rest[:endstyle + 8] + findings + rest[endstyle + 8:]
            else:
                html = prefix + findings + rest
        else:
            html = prefix + findings + rest
    else:
        html = findings + html
    if plan:
        spot = html.find('<section class="rc-tab-panel" data-panel="questions"')
        if spot == -1:
            spot = html.find('id="tab-questions"')
        if spot != -1:
            html = html[:spot] + plan + html[spot:]
        else:
            html += plan
    return html
