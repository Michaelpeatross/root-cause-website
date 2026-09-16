"""Accessible glossary expanders and mobile-friendly report layout."""
import re
from html import escape

GLOSSARY = [
    ('Health Score', 'A 0-100 wellness summary from this scan. Higher usually means fewer markers in that system. It is not a lab result or a diagnosis.'),
    ('marker', 'An item name the scanner file listed for a body system. It is a scan note, not proof of disease.'),
    ('bioenergetic', 'The method behind this hair and saliva scan. It looks at patterns in the file. It is not a blood test, DNA test, or allergy test.'),
    ('sensitivity', 'A scan pattern that resonated with a food or substance. It is not an allergy or intolerance diagnosis.'),
    ('imbalance', 'A theme the scan highlighted as extra load. Everyday language for this area showed up, not a medical finding.'),
    ('bile flow', 'How the body moves bile to help digest fats. A loaded pattern can mean heavy meals sit too long. Not a gallbladder diagnosis.'),
    ('lymph', 'The body drainage network. A loaded pattern often reads as puffiness or slow bounce-back. Not an infection test.'),
    ('adrenal', 'Stress-reserve glands in everyday talk. Sleep and caffeine usually matter here. Not a hormone lab result.'),
    ('candida', 'A yeast-and-sugar theme on some scans. Cutting sweet drinks is a common experiment. Not a lab culture.'),
    ('HTMA', 'Hair tissue mineral analysis - a different test. A Root Cause report is not HTMA.'),
    ('practitioner', 'A licensed clinician you already see or choose to see. Ideas in this report are talking points, not orders.'),
]

BADGE_GLOSSARY = [
    ('High', 'Informational badge: this theme had more emphasis on this scan. Not a lab grade.'),
    ('Medium', 'Informational badge: mid-level emphasis on this scan. Not a lab grade.'),
    ('Low', 'Informational badge: quieter emphasis on this scan. Not a medical all-clear.'),
]

A11Y_CSS = """
.glossary-panel{border:1px solid #dceee8;border-radius:12px;background:#fff;margin:0 0 1.15rem;padding:.15rem .2rem}
.glossary-panel>summary{cursor:pointer;list-style:none;font-weight:700;color:#0b3d2a;padding:.85rem 1rem;min-height:44px;display:flex;align-items:center;justify-content:space-between;gap:.5rem}
.glossary-panel>summary::-webkit-details-marker{display:none}
.glossary-panel>summary:after{content:"Show";font-weight:600;font-size:.8rem;color:#0d5c4d;background:#e8f5f1;border-radius:999px;padding:.2rem .65rem}
.glossary-panel[open]>summary:after{content:"Hide"}
.glossary-panel>summary:focus-visible{outline:3px solid #0d5c4d;outline-offset:2px}
.glossary-list{margin:0;padding:.15rem .85rem 1rem;display:grid;gap:.55rem}
.glossary-item{border-top:1px solid #e7f0ec;padding-top:.55rem}
.glossary-item dt{font-weight:700;color:#0b3d2a;margin:0 0 .15rem}
.glossary-item dd{margin:0;color:#334;font-size:.9rem;line-height:1.45}
.jargon{display:inline}
.jargon-term{display:inline;border-bottom:1px dotted #0d5c4d;cursor:help;background:transparent;color:inherit;font:inherit;padding:0;border-left:0;border-right:0;border-top:0;border-radius:0}
.jargon-term:focus-visible{outline:3px solid #0d5c4d;outline-offset:2px;border-radius:3px}
.jargon-pop{display:none;margin:.35rem 0 .5rem;padding:.55rem .7rem;background:#f4faf7;border:1px solid #c5ddd5;border-radius:8px;color:#234;font-size:.86rem;line-height:1.4;font-weight:400}
.jargon[open] .jargon-pop{display:block}
.wellness-report,.wellness-report-view{max-width:100%;overflow-wrap:anywhere}
@media (max-width:720px){
  .wellness-banner,.top3-item,.sys-plain-card,.wellness-theme-card{padding:.85rem .8rem}
  .wellness-banner h2,.top3 h2{font-size:1.15rem}
  .top3-item{grid-template-columns:1fr}
  .top3-head,.info-badge-legend,.sys-summary-right,.body-system-summary{flex-wrap:wrap}
  .sys-summary-right{width:100%;justify-content:flex-start}
  .sys-plain-grid,.wellness-theme-grid{grid-template-columns:1fr}
  .health-overall-card{padding:1rem .9rem}
  .health-score-number{font-size:2rem}
  .health-score-bar{height:16px}
  .health-score-bar.compact{height:12px}
  .report-card-header{flex-direction:column;align-items:stretch;gap:.75rem}
  .report-card-header .btn,.scan-view-tabs .btn{width:100%;text-align:center;min-height:44px}
  .container{padding-left:.75rem;padding-right:.75rem}
}
@media (prefers-reduced-motion:reduce){.health-score-fill{transition:none}}
"""


def glossary_panel_html():
    items = []
    for term, meaning in GLOSSARY + BADGE_GLOSSARY:
        items.append('<div class="glossary-item"><dt>' + escape(term) + '</dt><dd>' + escape(meaning) + '</dd></div>')
    return (
        '<details class="glossary-panel" id="report-glossary">'
        '<summary>Words used in this report</summary>'
        '<p class="glossary-lead" style="margin:0 1rem .65rem;color:#3d5c55;font-size:.9rem;">'
        'Tap a dotted word in the report, or open a term here. Definitions are informational only.</p>'
        '<dl class="glossary-list">' + ''.join(items) + '</dl></details>'
    )


def _jargon_markup(term, meaning):
    return (
        '<details class="jargon"><summary class="jargon-term">' + escape(term) + '</summary>'
        '<span class="jargon-pop" role="note">' + escape(meaning) + '</span></details>'
    )


def link_jargon(html):
    if not html:
        return html
    for term, meaning in GLOSSARY:
        if 'class="jargon-term">' + escape(term) in html:
            continue
        pattern = r'(?<![A-Za-z0-9])(' + re.escape(term) + r')(?![A-Za-z0-9])'
        replacement = _jargon_markup(term, meaning)
        parts = re.split(r'(<[^>]+>)', html)
        found = False
        out = []
        for part in parts:
            if found or (part.startswith('<') and part.endswith('>')):
                out.append(part)
                continue
            new_part, n = re.subn(pattern, replacement, part, count=1, flags=re.I)
            out.append(new_part)
            if n:
                found = True
        html = ''.join(out)
    return html


def enhance_score_bars(html):
    if not html:
        return html
    def add_meter(match):
        classes, width = match.group(1), match.group(2)
        try:
            num = max(0, min(100, int(float(width))))
        except ValueError:
            num = 0
        return (
            '<div class="health-score-bar%s" role="meter" aria-label="Health Score" aria-valuemin="0" aria-valuemax="100" aria-valuenow="%s">'
            '<div class="health-score-fill" style="width:%s%%"></div></div>' % (classes, num, num)
        )
    return re.sub(
        r'<div class="health-score-bar([^"]*)"><div class="health-score-fill[^"]*"\s+style="width:\s*([0-9.]+)%"></div></div>',
        add_meter, html, flags=re.I,
    )


def apply_report_a11y(html):
    if not html or len(html.strip()) < 40:
        return html
    if 'id="report-glossary"' not in html:
        panel = glossary_panel_html()
        if 'id="your-top-priorities"' in html:
            html = html.replace('<section class="top3" id="your-top-priorities"', panel + '<section class="top3" id="your-top-priorities"', 1)
        elif 'class="wellness-banner"' in html:
            html = re.sub(r'(</aside>)', r'\1' + panel, html, count=1)
        else:
            html = panel + html
    html = link_jargon(html)
    html = enhance_score_bars(html)
    if '.glossary-panel{' not in html:
        if '</style>' in html:
            html = html.replace('</style>', A11Y_CSS + '</style>', 1)
        else:
            html = '<style>' + A11Y_CSS + '</style>' + html
    return html
