"""Plain-English body-system cards for wellness reports."""
import re
from html import escape

SYSTEM_CLIENT_COPY = {
    'dermal': ('Skin, hair, and the outer barrier can feel reactive when this system is loaded. Dryness, itch, or slow repair after irritation are the everyday version of that pattern.', 'Ask whether recent products, showers, or diet changes line up with skin flares, and whether a simple barrier routine is worth trying before adding more products.'),
    'nervous': ('This system is the wiring for stress, focus, and sleep. When it is loaded, days can feel wired-and-tired or hard to switch off at night.', 'Mention sleep timing, caffeine, and how you recover from stress. Ask what a basic sleep or nervous-system check would look like if symptoms persist.'),
    'respiratory': ('Breathing comfort and air exchange sit here. Congestion or feeling winded on stairs can be the day-to-day clue. This scan is not a lung test.', 'Bring up snoring, daytime fatigue, or shortness of breath. Ask whether indoor air, allergies, or a breathing evaluation is the next clinical step.'),
    'digestive': ('This is how food is broken down and how comfortable you feel after meals. Bloat, urgency, or heaviness after eating often show up when this system is busy.', 'Describe meal timing, fiber, and foods that reliably bother you. Ask about a simple elimination experiment versus tests if symptoms are ongoing.'),
    'pancreas': ('Blood-sugar rhythm and digestive enzymes live here. Energy crashes after sweet drinks or large refined-carb meals are a common everyday signal.', 'Share what you eat at breakfast and whether you get shaky or sleepy after sweets. Ask if a standard glucose or A1C check is due.'),
    'liver_gallbladder': ('Processing fats and filtering what you eat and drink sit in this system. Heavy or fried meals that sit too long are the usual lived experience.', 'Talk about alcohol, late dinners, and right-sided fullness after fatty food. Ask which labs or imaging, if any, match those symptoms.'),
    'metabolism': ('This is cellular energy - how you turn food into fuel. Flat afternoons and slow recovery after ordinary days often pair with this pattern.', 'Ask about protein at meals, walking after eating, and whether thyroid or iron labs are already on file.'),
    'reproductive': ('Kidneys, bladder, and reproductive pathways share this grouping. Fluid timing or urinary urgency can be the practical clues - not a fertility diagnosis.', 'Mention cycle, prostate, or urinary symptoms if you have them. Ask which standard labs your clinician would use first.'),
    'hormones': ('Hormone rhythm affects energy, mood, sleep, and temperature. This is a scan pattern, not a hormone blood-test result.', 'Describe cycle, sleep, and temperature changes. Ask whether a standard hormone or thyroid panel is appropriate for your symptoms.'),
    'muscles': ('Muscles, joints, and recovery sit here. Stiffness after rest or slow bounce-back from ordinary activity is the everyday read.', 'Talk about training load, lingering aches, and minerals in your diet. Ask what a conservative recovery plan would include.'),
    'blood': ('Blood-quality signals are about transport and oxygen delivery in the scan picture. This is not a laboratory CBC.', 'If you have fatigue, unusual bruising, or no recent bloodwork, ask your clinician whether a standard panel is due.'),
    'cardiovascular': ('Circulation and heart-load patterns show up as stamina or how hard ordinary activity feels. This is not an EKG or stress test.', 'Share family history, blood pressure readings, and exercise tolerance. Ask which basic heart-health checks are already appropriate for your age.'),
    'lymph': ('Drainage and tissue clearing live here. Puffiness or slow recovery is the common translation.', 'Ask about movement, hydration, and whether swelling in a specific area should be examined rather than only watched.'),
    'immune': ('Immune load is the scan way of saying defenses were busy. Frequent lingering almost-sick weeks often sit next to this theme.', 'Describe infections, allergies, or recovery time. Ask what a reasonable workup looks like if you keep getting knocked down.'),
}

SYS_PLAIN_CSS = ('.sys-plain-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.7rem;margin:.75rem 0}.sys-plain-card{background:#f7fbf9;border:1px solid #dceee8;border-radius:10px;padding:.75rem .85rem}.sys-plain-card.discuss{background:#fffaf3;border-color:#f1e0c2}.sys-plain-card h4{margin:0 0 .35rem;color:#0b3d2a;font-size:.92rem}.sys-plain-card p{margin:0;color:#334;font-size:.88rem;line-height:1.45}.sys-plain-note{margin-top:.4rem!important;color:#8a6a32!important;font-size:.78rem!important}')

def plain_blocks_html(system_id):
    copy = SYSTEM_CLIENT_COPY.get(system_id)
    if copy:
        means, ideas = copy
    else:
        means = 'This grouping collects scan markers that landed in this body system. Open the list only if you want the raw names.'
        ideas = 'Bring the symptoms you actually feel to your practitioner and ask which standard checks, if any, fit those symptoms.'
    return ('<div class="sys-plain-grid"><article class="sys-plain-card"><h4>What this means in plain English</h4><p>' + escape(means) + '</p></article><article class="sys-plain-card discuss"><h4>Ideas to discuss with your practitioner</h4><p>' + escape(ideas) + '</p><p class="sys-plain-note">Talking points only - not a prescription, lab order, or treatment plan.</p></article></div>')

def inject_system_plain_cards(html):
    if not html:
        return html
    def _insert(match):
        system_id = match.group(2)
        existing = match.group(5) or ''
        if 'What this means in plain English' in existing or 'What this means in plain English' in match.group(3):
            return match.group(0)
        return match.group(1) + system_id + '"' + match.group(3) + match.group(4) + plain_blocks_html(system_id) + existing
    updated = re.sub(r'(id="body-system-)([a-z_]+)"([\s\S]*?)(<p class="body-system-def">[\s\S]*?</p>)(\s*<div class="sys-plain-grid">[\s\S]*?</div>)?', _insert, html, flags=re.I)
    if '.sys-plain-grid{' not in updated and '</style>' in updated:
        updated = updated.replace('</style>', SYS_PLAIN_CSS + '</style>', 1)
    elif '.sys-plain-grid{' not in updated:
        updated = '<style>' + SYS_PLAIN_CSS + '</style>' + updated
    try:
        from report_a11y import apply_report_a11y
        updated = apply_report_a11y(updated)
    except Exception:
        pass
    try:
        from report_tabs import apply_report_tabs
        updated = apply_report_tabs(updated)
    except Exception:
        pass
    return updated
