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
    """Map imbalance count to a readable stress label (no raw % shown)."""
    score = max(MIN_SCORE, BASE_SCORE - marker_count * DEDUCTION_PER_MARKER)
    for threshold, label, css in STRESS_LEVELS:
        if score >= threshold:
            return label, css, score
    return 'Chronic Weakness', 'stress-severe', score


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


def render_body_overview_html(overview):
    """Render the Body Overview section with expandable system details."""
    active = [s for s in (overview or []) if s.get('markers')]
    if not active:
        return ''

    cards = []
    for system in active:
        marker_items = ''.join(
            f'<li>{escape(m["name"])}</li>' for m in system['markers']
        )
        cards.append(
            f'<details class="body-system-card" id="body-system-{escape(system["id"])}">'
            f'<summary class="body-system-summary">'
            f'<span class="body-system-name">{escape(system["name"])}</span>'
            f'<span class="stress-badge {system["stress_css"]}">'
            f'{escape(system["stress_label"])}</span>'
            f'</summary>'
            f'<div class="body-system-detail">'
            f'<p class="body-system-def">{escape(system["definition"])}</p>'
            f'<h4>Stress markers in your scan</h4>'
            f'<ul class="body-marker-list">{marker_items}</ul>'
            f'</div>'
            f'</details>'
        )

    legend = ''.join(
        f'<span class="legend-item"><span class="stress-badge {css}">{label}</span></span>'
        for _threshold, label, css in STRESS_LEVELS
    )

    return (
        '<section class="scan-section page-break" id="body-overview">'
        '<h2>Body Overview</h2>'
        '<p class="scan-lead">Your scan tested multiple areas of the body. '
        'Each system below shows your overall stress level based on markers found '
        f'(3% deduction per item tested with imbalance). Click a system to see its '
        'definition and your stress markers.</p>'
        '<div class="scan-legend body-overview-legend">'
        '<span class="legend-title">Stress scale:</span>'
        f'{legend}'
        '</div>'
        f'<div class="body-overview-grid">{"".join(cards)}</div>'
        '</section>'
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
    """True when the line is only a sensitivity category label."""
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
    """Parse all sensitivity categories; always return every group."""
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
    """Parse toxin categories into short, readable marker labels."""
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
    """Parse nutrients into categorized item lists."""
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
    """Render grouped columns; only categories with detected markers."""
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