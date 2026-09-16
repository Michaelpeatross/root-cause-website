"""Placeholder sample report using the same wellness wrap as live client reports."""

SAMPLE_CLIENT = 'Alex Sample'
SAMPLE_EMAIL = 'sample@example.com'
SAMPLE_TITLE = 'Sample Full Scan (placeholder)'

SAMPLE_RAW = """Full Scan
Alex Sample - 01/15/2026

Energetic System Performance
Most significantly stressed: intestine, liver, candida, gallbladder, lymph, digestion, adrenal, immune, thyroid
Driving some of your systems down: sugar load, late meals, low daily movement, fragrance exposure

Energetic Sensitivities
Grains
Wheat
Gluten-containing grains
Dairy
Cow milk
Cheese pattern
Eggs
Chicken egg
Environmental
Fragrance blend
Dust mite pattern
Mold spore pattern
Additives
Artificial colors
Artificial sweeteners

Energetic Nutrients
Vitamins
Vitamin D
B-complex pattern
Vitamin B12 pattern
Minerals
Magnesium
Zinc
Enzymes
Digestive enzyme pattern

Energetic Toxins
Molds
Household mold pattern
Chemicals
Fragrance chemicals
Cleaning-product pattern

Energetic Hormonal Imbalances
Low Vitamin D related rhythm
High evening wired-tired pattern

Metabolic Test Results
YOU TESTED WITH AN IMBALANCE IN: Digestion comfort
→ What it is A scan pattern around how food sits after eating.
→ What this means Heaviness or bloat after larger meals can be the everyday version of this theme.
→ Lifestyle hacks Simpler meals and less constant snacking are educational ideas to discuss, not a treatment plan.

YOU TESTED WITH AN IMBALANCE IN: Afternoon energy
→ What it is A metabolic energy pattern on this wellness scan.
→ What this means Flat afternoons after sweet drinks are a common lived clue.
→ Lifestyle hacks Protein at breakfast and a short walk after the largest meal are talking points only.

Better Sleep Scan Results
YOU TESTED WITH AN IMBALANCE IN: Sleep timing
→ What it is A sleep-rhythm pattern from the scan file.
→ What this means Trouble winding down can sit next to this theme.
→ Lifestyle hacks A consistent bedtime is a simple first experiment to discuss.

Hormone Test Results
Low Vitamin D related rhythm
High evening wired-tired pattern

Personalized Client Summary
This is a placeholder sample written like a real Root Cause wellness report. Health Scores and top priorities come first. Lists from the scanner file stay folded. Nothing here is a diagnosis, allergy result, lab value, or treatment plan.

Next Steps
1. Read Your top 3 priorities in everyday language.
2. Open one body-system card that matches how you feel day to day.
3. Bring the Questions tab talking points to a licensed clinician if symptoms persist.

Balancing Remedies
Nutritional Supplements
Sample magnesium glycinate idea
Educational product idea tied to the energy theme. Not a prescription or dose.
$0.00
Sample digestive bitters idea
Educational lifestyle product idea for discussion only.
$0.00

Disclaimer
These statements have not been evaluated by the Food and Drug Administration. This service is for educational purposes only and is not intended to diagnose, treat, cure, or prevent any disease. This sample is placeholder content. It is not medical advice, not an allergy test, and not a substitute for a licensed clinician.
"""

_SAMPLE_BANNER = (
    '<aside class="sample-placeholder-banner" role="note">'
    '<strong>Sample only — placeholder data.</strong> This page uses invented results for '
    '<em>Alex Sample</em> so you can see the same reusable template logged-in clients get. '
    'It is not a real scan, not your results, not a diagnosis, not an allergy test, '
    'and not medical advice.</aside>'
)

_SAMPLE_CSS = (
    '<style>.sample-placeholder-banner{background:#fff6e8;border:1px solid #f1d7a6;'
    'border-radius:12px;padding:.85rem 1rem;margin:0 0 1rem;color:#5c4316;line-height:1.45}'
    '.sample-placeholder-banner strong{color:#7a4b00}</style>'
)

_FALLBACK = (
    _SAMPLE_CSS + _SAMPLE_BANNER +
    '<div class="wellness-report" id="wellness-report-chrome">'
    '<aside class="wellness-banner">'
    '<h2>Your wellness report</h2>'
    '<p>A live report uses Health Scores, top 3 priorities, body-system cards, '
    'and optional food or supplement tabs. Informational only.</p>'
    '<div class="wellness-pill-row">'
    '<span class="wellness-pill">Informational only</span>'
    '<span class="wellness-pill">Not a diagnosis</span>'
    '<span class="wellness-pill">Not an allergy test</span>'
    '<span class="wellness-pill">Not a substitute for a clinician</span>'
    '</div></aside>'
    '<p class="wellness-footnote">Wellness information only. Not a medical diagnosis, '
    'treatment, allergy test, DNA test, HTMA, or tool for detecting disease.</p>'
    '</div>'
)

_cache = {'html': None}


def _attach_sample_banner(html):
    if not html:
        return _FALLBACK
    if 'sample-placeholder-banner' in html:
        return html
    if '<div class="wellness-report"' in html:
        return html.replace(
            '<div class="wellness-report"',
            _SAMPLE_CSS + _SAMPLE_BANNER + '<div class="wellness-report"',
            1,
        )
    return _SAMPLE_CSS + _SAMPLE_BANNER + html


def build_sample_report_html():
    """Same generate + wrap pipeline used for saved client reports. Cached."""
    if _cache['html']:
        return _cache['html']
    try:
        from wellness_template import render_wellness_report
        html = render_wellness_report(
            SAMPLE_RAW,
            client_name=SAMPLE_CLIENT,
            title=SAMPLE_TITLE,
            email=SAMPLE_EMAIL,
        )
    except Exception as exc:
        print('[Root Cause] sample render_wellness_report failed: %s' % exc)
        try:
            from scan_template import generate_template_report_html
            from wellness_template import wrap_wellness_report
            html = generate_template_report_html(
                SAMPLE_EMAIL,
                SAMPLE_TITLE,
                SAMPLE_RAW,
                client_name=SAMPLE_CLIENT,
            )
            html = wrap_wellness_report(
                html, client_name=SAMPLE_CLIENT, title=SAMPLE_TITLE, raw_data=SAMPLE_RAW,
            )
        except Exception as exc2:
            print('[Root Cause] sample wrap fallback failed: %s' % exc2)
            html = _FALLBACK
    try:
        from system_plain import inject_system_plain_cards
        html = inject_system_plain_cards(html)
    except Exception:
        pass
    html = _attach_sample_banner(html or _FALLBACK)
    _cache['html'] = html
    return html
