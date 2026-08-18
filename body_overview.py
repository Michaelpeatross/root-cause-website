"""Body Overview: group scan markers into body systems with stress levels."""
import re
from html import escape

DEDUCTION_PER_MARKER = 3
BASE_SCORE = 100
MIN_SCORE = 20

STRESS_LEVELS = (
    (91, 'Minor Stress', 'stress-minor'),
    (71, 'Stress', 'stress-moderate'),
    (51, 'Chronic Stress', 'stress-chronic'),
    (31, 'Weakness', 'stress-weakness'),
    (0, 'Chronic Weakness', 'stress-severe'),
)

BODY_SYSTEMS = [
    {
        'id': 'dermal',
        'name': 'Dermal',
        'definition': (
            'Your skin, hair, and outer protective barriers. This system reflects '
            'how your body responds to topical stressors, hydration, and repair.'
        ),
        'keywords': [
            'integumentary', 'dermal', 'skin', 'scalp', 'hair', 'epiderm', 'collagen',
            'cutaneous', 'sweat', 'sebaceous',
        ],
    },
    {
        'id': 'nervous',
        'name': 'Nervous',
        'definition': (
            'Your brain, nerves, and communication pathways — including stress response, '
            'focus, sleep signals, and coordination between body systems.'
        ),
        'keywords': [
            'nervous', 'nerve', 'brain', 'neural', 'pituitary', 'pineal', 'governing vessel',
            'peripheral', 'central nervous', 'hypothalamus', 'orexin', 'autonomic',
            'cerebral', 'neurolog',
        ],
    },
    {
        'id': 'respiratory',
        'name': 'Respiratory',
        'definition': (
            'Your lungs and breathing pathways — oxygen exchange, airway health, '
            'and how well your body delivers oxygen to cells.'
        ),
        'keywords': [
            'respiratory', 'lung', 'bronch', 'breath', 'oxygen', 'airway', 'pulmonary',
            'sleep apnea', 'sinus',
        ],
    },
    {
        'id': 'digestive',
        'name': 'Digestive',
        'definition': (
            'Your stomach, intestines, and gut — breaking down food, absorbing nutrients, '
            'and maintaining a healthy digestive environment.'
        ),
        'keywords': [
            'digestive', 'stomach', 'gut', 'intestin', 'colon', 'bowel', 'esophag',
            'duodenum', 'ileum', 'digestion', 'gi tract', 'dysbiosis', 'galactosidase',
            'bloating', 'protease', 'lactase', 'bromelain',
        ],
    },
    {
        'id': 'pancreas',
        'name': 'Pancreas',
        'definition': (
            'Your pancreas — blood sugar balance, digestive enzyme production, '
            'and metabolic signaling.'
        ),
        'keywords': [
            'pancreas', 'pancreatic', 'insulin', 'glucagon', 'blood sugar', 'glucose',
        ],
    },
    {
        'id': 'liver_gallbladder',
        'name': 'Liver / Gallbladder',
        'definition': (
            'Your liver and gallbladder — detoxification, bile flow, fat processing, '
            'and filtering what enters your bloodstream.'
        ),
        'keywords': [
            'liver', 'gallbladder', 'gall bladder', 'bile', 'hepat', 'detox',
            'capillar', 'glucocerebrosidase', 'sluggish bile',
        ],
    },
    {
        'id': 'metabolism',
        'name': 'Metabolism',
        'definition': (
            'Your cellular energy engine — how efficiently your body creates and uses '
            'fuel at the mitochondrial and metabolic level.'
        ),
        'keywords': [
            'metabolism', 'metabolic', 'mitochondri', 'cellular metabolism', 'nadh',
            'krebs', 'keto', 'lactic acid', 'energy production', 'coq10', 'atp',
            'cellular energy',
        ],
    },
    {
        'id': 'reproductive',
        'name': 'Reproductive',
        'definition': (
            'Your reproductive and urinary pathways — hormones, organs, and balance '
            'related to fertility, elimination, and urogenital health.'
        ),
        'keywords': [
            'urogenital', 'reproductive', 'ovary', 'ovarian', 'prostate', 'uterus',
            'bladder', 'kidney', 'urinary', 'testosterone', 'estrogen', 'androstenedione',
            'progesterone', 'fertility',
        ],
    },
    {
        'id': 'hormones',
        'name': 'Hormones',
        'definition': (
            'Your endocrine signaling — glands and hormones that regulate mood, energy, '
            'weight, sleep, and overall hormonal rhythm.'
        ),
        'keywords': [
            'endocrine', 'hormone', 'hormonal', 'thyroid', 'adrenal', 'cortisol', 'acth',
            'tsh', 'parathyroid', 'dhea', 'hormone precursor',
        ],
    },
    {
        'id': 'muscles',
        'name': 'Muscles',
        'definition': (
            'Your muscles, joints, and structural support — movement, strength, '
            'recovery, and physical resilience.'
        ),
        'keywords': [
            'locomotor', 'muscle', 'muscular', 'joint', 'bone', 'skeletal', 'spine',
            'tendon', 'ligament', 'structural', 'movement', 'calcium balance',
        ],
    },
    {
        'id': 'blood',
        'name': 'Blood',
        'definition': (
            'Your blood and related markers — oxygen delivery, nutrient transport, '
            'and overall blood quality signals.'
        ),
        'keywords': [
            'blood', 'hemoglobin', 'hemat', 'anemia', 'platelet', 'clotting', 'erythro',
        ],
    },
    {
        'id': 'cardiovascular',
        'name': 'Cardiovascular',
        'definition': (
            'Your heart and circulation — blood flow, vessel health, and cardiovascular '
            'resilience under stress.'
        ),
        'keywords': [
            'cardiovascular', 'heart', 'circulat', 'vessel', 'arter', 'vein',
            'lipoprotein', 'cholesterol', 'lipid', 'cardiac',
        ],
    },
    {
        'id': 'lymph',
        'name': 'Lymph',
        'definition': (
            'Your lymphatic system — drainage, immune transport, and clearing waste '
            'from tissues.'
        ),
        'keywords': [
            'lymph', 'lymphatic', 'drainage', 'lymph node',
        ],
    },
    {
        'id': 'immune',
        'name': 'Immune',
        'definition': (
            'Your immune defenses — how your body identifies stressors, inflammation, '
            'and recovery from environmental or microbial challenges.'
        ),
        'keywords': [
            'immune', 'immunity', 'inflamm', 'pathogen', 'infection', 'candida',
            'autoimmune', 'antibod',
        ],
    },
]

_SENSITIVITY_ALIASES = {
    'grain': 'Grains',
    'grains': 'Grains',
    'additives': 'Additives',
    'addiitives': 'Additives',
    'addiives': 'Additives',
    'dairy': 'Dairy',
    'environmental': 'Environmental',
    'beverages': 'Beverages',
    'dairyalternative': 'Dairy Alternatives',
    'dairy alternaive': 'Dairy Alternatives',
    'fish': 'Fish',
    'fruit': 'Fruit',
    'ingredients': 'Ingredients',
    'legume': 'Legumes',
    'legumes': 'Legumes',
    'meat': 'Meat',
    'nut': 'Nuts',
    'nuts': 'Nuts',
    'shellfish': 'Shellfish',
    'shell sh': 'Shellfish',
    'spice': 'Spices',
    'spices': 'Spices',
    'sugar': 'Sugar',
    'vegetable': 'Vegetables',
    'vegetables': 'Vegetables',
}

SENSITIVITY_CATEGORIES = [
    'Grains', 'Additives', 'Dairy', 'Environmental', 'Beverages',
    'Fish', 'Fruit', 'Ingredients', 'Legumes', 'Meat', 'Nuts',
    'Shellfish', 'Spices', 'Vegetables',
]

NUTRIENT_CATEGORIES = [
    'Vitamins', 'Enzymes', 'Fatty Acids', 'Amino Acids', 'Minerals',
]

TOXIN_CATEGORIES = [
    'Bacteria', 'Parasites', 'Metals', 'Molds', 'Chemicals',
]


def score_to_stress_level(marker_count):
    """Map imbalance count to a readable stress label and numeric Health Score (higher = better)."""
    score = max(MIN_SCORE, BASE_SCORE - marker_count * DEDUCTION_PER_MARKER)
    for threshold, label, css in STRESS_LEVELS:
        if score >= threshold:
            return label, css, score
    return 'Chronic Weakness', 'stress-severe', score


def overall_health_score(overview):
    """Average Health Score across systems that have markers; fall back to 100 if none."""
    active = [s for s in (overview or []) if s.get('markers')]
    if not active:
        return 100
    total = sum(s.get('score', BASE_SCORE) for s in active)
    return max(MIN_SCORE, min(100, int(round(total / len(active)))))


def score_color_css(score):
    """Return a CSS color class or inline-friendly gradient stop for the score bar."""
    if score >= 91:
        return 'health-excellent'
    if score >= 71:
        return 'health-good'
    if score >= 51:
        return 'health-fair'
    if score >= 31:
        return 'health-low'
    return 'health-critical'


def classify_marker(marker):
    """Assign a scan marker to the best-matching body system."""
    lower = (marker or '').lower()
    best = None
    best_hits = 0
    for system in BODY_SYSTEMS:
        hits = sum(1 for kw in system['keywords'] if kw in lower)
        if hits > best_hits:
            best_hits = hits
            best = system
    if best:
        return best['id']
    return 'metabolism'


def collect_scan_markers(scan_text, sections, imbalance_cards, hormone_items):
    """Gather tested items with imbalance or resistance from the full scan."""
    markers = []
    seen = set()

    def add(name, source=''):
        name = re.sub(r'\s+', ' ', (name or '').strip())
        if not name or len(name) < 2:
            return
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        markers.append({'name': name, 'source': source})

    sys_text = sections.get('system_performance', '')
    if not sys_text:
        first = re.search(r'energ.{0,6}c\s+sensiti', scan_text, re.I)
        sys_text = scan_text[:first.start()] if first else scan_text[:5000]

    stressed = re.search(
        r'most\s+signific[^\n]*stressed:\s*([^\n]+)',
        sys_text,
        re.I,
    )
    if stressed:
        for part in re.split(r',|(?:\band\b)', stressed.group(1)):
            add(part.strip(), 'system performance')

    driving = re.search(
        r'driving some of your systems down[:\s]*([^\n]+)',
        sys_text,
        re.I,
    )
    if driving:
        for part in re.split(r',|(?:\band\b)', driving.group(1)):
            add(part.strip(), 'system performance')

    for card in imbalance_cards or []:
        add(card.get('name', ''), 'imbalance')

    for hormone in hormone_items or []:
        level = hormone.get('level', '').strip()
        name = hormone.get('name', '').strip()
        if name:
            add(f'{level} {name}'.strip(), 'hormone')

    return markers


def build_body_overview(scan_text, sections, imbalance_cards, hormone_items):
    """Group markers into body systems with calculated stress levels."""
    markers = collect_scan_markers(scan_text, sections, imbalance_cards, hormone_items)
    grouped = {s['id']: [] for s in BODY_SYSTEMS}

    for marker in markers:
        system_id = classify_marker(marker['name'])
        grouped[system_id].append(marker)

    overview = []
    for system in BODY_SYSTEMS:
        system_markers = grouped[system['id']]
        label, css, score = score_to_stress_level(len(system_markers))
        overview.append({
            'id': system['id'],
            'name': system['name'],
            'definition': system['definition'],
            'markers': system_markers,
            'stress_label': label,
            'stress_css': css,
            'score': score,
        })
    return overview


def filter_nonempty_groups(groups):
    """Drop categories that have no detected markers."""
    return {cat: items for cat, items in (groups or {}).items() if items}


def render_body_overview_html(overview, previous_scores=None):
    """Render Body Overview with overall + per-system Health Scores and color charts."""
    previous_scores = previous_scores or {}
    systems_to_show = overview or []
    if not systems_to_show:
        return ''

    overall = overall_health_score(overview)
    overall_css = score_color_css(overall)
    prev_overall = previous_scores.get('overall')
    progress_html = ''
    if prev_overall is not None:
        try:
            prev_overall = int(prev_overall)
            delta = overall - prev_overall
            if delta > 0:
                progress_html = (
                    f'<span class="health-progress up">Previous {prev_overall} → '
                    f'<strong>{overall}</strong> (+{delta})</span>'
                )
            elif delta < 0:
                progress_html = (
                    f'<span class="health-progress down">Previous {prev_overall} → '
                    f'<strong>{overall}</strong> ({delta})</span>'
                )
            else:
                progress_html = (
                    f'<span class="health-progress same">Previous {prev_overall} → '
                    f'<strong>{overall}</strong> (no change)</span>'
                )
        except (TypeError, ValueError):
            progress_html = ''

    overall_block = (
        '<div class="health-overall-card">'
        '<div class="health-overall-header">'
        '<h3>Your Overall Health Score</h3>'
        f'<div class="health-score-number {overall_css}">{overall}</div>'
        '</div>'
        f'{progress_html}'
        '<p class="health-overall-note">This evaluated score (0–100) combines findings from your '
        'bioenergetic scan and any medical information on file. Higher is better. '
        'It reflects how balanced the main body systems appear on this evaluation.</p>'
        f'<div class="health-score-bar"><div class="health-score-fill {overall_css}" '
        f'style="width:{overall}%"></div></div>'
        '<div class="health-score-scale"><span>Needs support</span><span>Balanced</span></div>'
        '</div>'
    )

    cards = []
    for system in systems_to_show:
        has_markers = bool(system.get('markers'))
        score = system.get('score', BASE_SCORE) if has_markers else BASE_SCORE
        css = system.get('stress_css', 'stress-minor') if has_markers else 'stress-minor'
        color_css = score_color_css(score) if has_markers else 'health-excellent'
        label = system.get('stress_label', 'Minor Stress') if has_markers else 'No major markers'
        marker_count = len(system.get('markers') or [])
        prev_sys = previous_scores.get(system['id'])
        sys_progress = ''
        if prev_sys is not None and has_markers:
            try:
                prev_sys = int(prev_sys)
                d = score - prev_sys
                if d > 0:
                    sys_progress = f'<span class="sys-progress up">Prev {prev_sys} → {score} (+{d})</span>'
                elif d < 0:
                    sys_progress = f'<span class="sys-progress down">Prev {prev_sys} → {score} ({d})</span>'
                else:
                    sys_progress = f'<span class="sys-progress same">Prev {prev_sys} → {score}</span>'
            except (TypeError, ValueError):
                pass

        marker_summary = (
            f'<p class="marker-summary">{marker_count} stress marker'
            f'{"s" if marker_count != 1 else ""} found</p>'
            if has_markers else
            '<p class="marker-summary muted">No significant stress markers in this system</p>'
        )
        marker_items = ''
        if has_markers:
            marker_items = (
                '<ul class="body-marker-list">'
                + ''.join(f'<li>{escape(m["name"])}</li>' for m in system['markers'])
                + '</ul>'
            )

        cards.append(
            f'<details class="body-system-card" id="body-system-{escape(system["id"])}">'
            f'<summary class="body-system-summary">'
            f'<div class="sys-summary-left">'
            f'<span class="body-system-name">{escape(system["name"])}</span>'
            f'{sys_progress}'
            f'</div>'
            f'<div class="sys-summary-right">'
            f'<span class="health-score-pill {color_css}">{score}</span>'
            f'<span class="stress-badge {css}">{escape(label)}</span>'
            f'</div>'
            f'</summary>'
            f'<div class="body-system-detail">'
            f'<div class="health-score-bar compact"><div class="health-score-fill {color_css}" '
            f'style="width:{score}%"></div></div>'
            f'<p class="body-system-def">{escape(system["definition"])}</p>'
            f'{marker_summary}'
            f'{marker_items}'
            f'</div>'
            f'</details>'
        )

    legend = ''.join(
        f'<span class="legend-item"><span class="stress-badge {css}">{label}</span></span>'
        for _threshold, label, css in STRESS_LEVELS
    )

    styles = (
        '<style>'
        '.health-overall-card{background:linear-gradient(135deg,#f0f9f6,#e8f5f1);border:1px solid #b8d9cf;'
        'border-radius:14px;padding:1.35rem 1.5rem;margin:1.25rem 0 1.5rem;box-shadow:0 2px 8px rgba(13,92,77,.06)}'
        '.health-overall-header{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}'
        '.health-overall-header h3{margin:0;font-size:1.15rem;color:#0d5c4d}'
        '.health-score-number{font-size:2.4rem;font-weight:800;line-height:1;min-width:3.2rem;text-align:center}'
        '.health-score-number.health-excellent,.health-score-pill.health-excellent{color:#0d7a4f}'
        '.health-score-number.health-good,.health-score-pill.health-good{color:#2d8a4e}'
        '.health-score-number.health-fair,.health-score-pill.health-fair{color:#b8860b}'
        '.health-score-number.health-low,.health-score-pill.health-low{color:#c45c26}'
        '.health-score-number.health-critical,.health-score-pill.health-critical{color:#b33a3a}'
        '.health-overall-note{font-size:.92rem;color:#3d5c55;margin:.65rem 0 .9rem;line-height:1.45}'
        '.health-score-bar{height:12px;background:#dceae5;border-radius:999px;overflow:hidden;margin:.35rem 0}'
        '.health-score-bar.compact{height:8px;margin:.5rem 0 .75rem}'
        '.health-score-fill{height:100%;border-radius:999px;transition:width .4s ease}'
        '.health-score-fill.health-excellent{background:linear-gradient(90deg,#34d399,#059669)}'
        '.health-score-fill.health-good{background:linear-gradient(90deg,#6ee7b7,#10b981)}'
        '.health-score-fill.health-fair{background:linear-gradient(90deg,#fcd34d,#d97706)}'
        '.health-score-fill.health-low{background:linear-gradient(90deg,#fdba74,#ea580c)}'
        '.health-score-fill.health-critical{background:linear-gradient(90deg,#fca5a5,#dc2626)}'
        '.health-score-scale{display:flex;justify-content:space-between;font-size:.75rem;color:#6b857e;margin-top:.25rem}'
        '.health-progress{display:inline-block;margin-top:.4rem;font-size:.9rem;padding:.25rem .65rem;border-radius:6px;'
        'background:#fff;border:1px solid #c5ddd5}'
        '.health-progress.up{color:#0d7a4f;border-color:#86efac}'
        '.health-progress.down{color:#b33a3a;border-color:#fca5a5}'
        '.health-progress.same{color:#5a6f6a}'
        '.health-score-pill{display:inline-flex;align-items:center;justify-content:center;min-width:2.4rem;'
        'padding:.2rem .5rem;border-radius:999px;font-weight:700;font-size:.95rem;background:#f0f9f6;border:1px solid #c5ddd5}'
        '.sys-summary-left{display:flex;flex-direction:column;gap:.2rem}'
        '.sys-summary-right{display:flex;align-items:center;gap:.5rem;flex-shrink:0}'
        '.sys-progress{font-size:.78rem;color:#5a6f6a}'
        '.sys-progress.up{color:#0d7a4f}'
        '.sys-progress.down{color:#b33a3a}'
        '.marker-summary{font-size:.9rem;margin:.4rem 0;color:#3d5c55}'
        '.marker-summary.muted{color:#8a9e98}'
        '.health-disclaimer-note{font-size:.82rem;color:#6b857e;margin-top:1.25rem;line-height:1.4}'
        '.body-system-summary{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}'
        '</style>'
    )

    grid_html = '<div class="body-overview-grid">' + ''.join(cards) + '</div>'

    return (
        '<section class="scan-section page-break" id="body-overview">'
        + styles
        + '<h2>Body Systems & Health Scores</h2>'
        + '<p class="scan-lead">Your scan evaluates key body systems. Each system receives a '
        + '<strong>Health Score</strong> (0–100, higher is better) based on the number and type of '
        + 'imbalance markers found. An overall score summarizes your current evaluation. '
        + 'When a previous scan is available, you will also see your progress.</p>'
        + overall_block
        + '<div class="scan-legend body-overview-legend">'
        + '<span class="legend-title">Stress scale:</span>'
        + legend
        + '</div>'
        + grid_html
        + '<p class="health-disclaimer-note">Health Scores are an educational evaluation derived from '
        + 'your bioenergetic scan and available medical context. They are not a medical diagnosis '
        + 'or biological age measurement.</p>'
        + '</section>'
    )


def _normalize_category_label(line):
    key = re.sub(r'[^a-z]', '', line.lower())
    if key in _SENSITIVITY_ALIASES:
        return _SENSITIVITY_ALIASES[key]
    if re.match(r'^addi[a-z]{0,6}ves?$', key):
        return 'Additives'
    if re.match(r'^dairyalterna[a-z]{0,6}ve?$', key):
        return 'Dairy Alternatives'
    if re.match(r'^shell[a-z]{0,6}sh$', key):
        return 'Shellfish'
    if key in ('grain', 'grains'):
        return 'Grains'
    return None


def _is_category_header_line(line):
    if not line:
        return False
    stripped = line.strip()
    if _normalize_category_label(stripped):
        return len(stripped.split()) <= 2
    for alias in _SENSITIVITY_ALIASES:
        if re.match(rf'^{re.escape(alias)}\s*$', stripped, re.I):
            return True
    return bool(re.match(r'^addi[a-z\s]{0,12}ves?\s*$', stripped, re.I))


def parse_sensitivity_groups(text):
    groups = {cat: [] for cat in SENSITIVITY_CATEGORIES}
    current = None
    for line in (text or '').split('\n'):
        line = line.strip()
        if not line:
            continue
        if _is_category_header_line(line):
            cat = _normalize_category_label(line) or _normalize_category_label(line.split()[0])
            if cat and cat in groups:
                current = cat
            continue
        cat = _normalize_category_label(line.split()[0] if line else '')
        if not cat:
            for alias, canonical in _SENSITIVITY_ALIASES.items():
                if re.match(rf'^{re.escape(alias)}\b', line, re.I):
                    cat = canonical
                    line = re.sub(rf'^{re.escape(alias)}\s*', '', line, flags=re.I).strip()
                    break
            if not cat and re.match(r'^addi[a-z]{0,6}ves?\b', line, re.I):
                cat = 'Additives'
                line = re.sub(r'^addi[a-z]{0,6}ves?\s*', '', line, flags=re.I).strip()
        if cat and cat in groups:
            current = cat
            if line and line.lower() != 'none' and not _is_category_header_line(line):
                groups[current].append(line)
            continue
        if current and current in groups and line.lower() != 'none':
            groups[current].append(line)
    return groups


def parse_toxin_groups(text):
    groups = {cat: [] for cat in TOXIN_CATEGORIES}
    aliases = {
        'bacteria': 'Bacteria',
        'parasites': 'Parasites',
        'metals': 'Metals',
        'mold': 'Molds',
        'molds': 'Molds',
        'chemicals': 'Chemicals',
    }
    current = None
    buffer = []

    def flush_buffer():
        nonlocal buffer
        if not current or not buffer:
            buffer = []
            return
        snippet = re.sub(r'\s+', ' ', ' '.join(buffer)).strip()
        if snippet and snippet.lower() != 'none':
            snippet = re.sub(r'^a resonating\s+', '', snippet, flags=re.I)
            snippet = snippet[0].upper() + snippet[1:] if snippet else snippet
            if len(snippet) > 110:
                snippet = snippet[:107].rsplit(' ', 1)[0] + '…'
            groups[current].append(snippet)
        buffer = []

    for line in (text or '').split('\n'):
        line = line.strip()
        if not line:
            continue
        first = re.sub(r'[^a-z]', '', line.split()[0].lower()) if line else ''
        cat = aliases.get(first)
        if cat:
            flush_buffer()
            current = cat
            rest = re.sub(rf'^{re.escape(line.split()[0])}\s*', '', line, count=1).strip()
            if rest and rest.lower() != 'none':
                buffer = [rest]
            else:
                buffer = []
            continue
        if line.lower() == 'none':
            flush_buffer()
            continue
        if current:
            if line.lower().startswith('a resonating'):
                flush_buffer()
            buffer.append(line)

    flush_buffer()
    return groups


def parse_nutrient_item_lists(text):
    groups = {cat: [] for cat in NUTRIENT_CATEGORIES}
    aliases = {
        'vitamins': 'Vitamins',
        'enzymes': 'Enzymes',
        'fattyacids': 'Fatty Acids',
        'fatty acids': 'Fatty Acids',
        'amino acids': 'Amino Acids',
        'minerals': 'Minerals',
    }
    sections = {}
    current = None
    buffer = []

    for line in (text or '').split('\n'):
        line = line.strip()
        if not line:
            continue
        lower_key = re.sub(r'[^a-z ]', '', line.lower()).strip()
        if re.match(r'^fa[a-z]{0,4}yacids?$', lower_key.replace(' ', '')):
            lower_key = 'fatty acids'
        if lower_key in aliases:
            if current and buffer:
                sections[current] = '\n'.join(buffer)
            current = aliases[lower_key]
            buffer = []
            continue
        if current:
            buffer.append(line)

    if current and buffer:
        sections[current] = '\n'.join(buffer)

    for cat, chunk in sections.items():
        for block in re.split(r'\n(?=[A-Z][A-Za-z0-9\-\(])', chunk):
            lines = [ln.strip() for ln in block.split('\n') if ln.strip()]
            if not lines:
                continue
            name = lines[0]
            lower = name.lower()
            if lower.startswith('sources') or lower.startswith('food sources'):
                continue
            if lower.startswith('dietary sources') or lower.startswith('found naturally'):
                continue
            if len(name) > 85:
                continue
            if re.match(r'^(and|or|the|with)\b', lower):
                continue
            if ',' in name and '(' not in name:
                continue
            if re.search(r'\b(sprouts|greens|beans|seeds|yogurt|fish|meat|oats)\b', lower):
                continue
            groups[cat].append(name)
    return groups


def render_category_section_html(title, lead, groups, show_empty=False):
    groups = filter_nonempty_groups(groups)
    if not groups:
        return ''
    html = '<div class="scan-columns">'
    for cat, items in groups.items():
        lis = ''.join(f'<li>{escape(i)}</li>' for i in items)
        html += (
            f'<div class="scan-col"><h4>{escape(cat)}</h4>'
            f'<ul class="scan-list">{lis}</ul></div>'
        )
    html += '</div>'
    return (
        f'<section class="scan-section page-break">'
        f'<h2>{escape(title)}</h2>'
        f'<p class="scan-lead">{escape(lead)}</p>'
        f'{html}</section>'
    )
