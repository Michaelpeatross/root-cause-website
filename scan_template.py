"""Parse bioenergetic scan text and render reports matching the Full Scan PDF template."""
import re
from html import escape
from datetime import datetime

SYSTEM_NAMES = [
    'Integumentary', 'Nervous', 'Respiratory', 'Digestive', 'Pancreas',
    'LiverGallbladder', 'Liver/Gallbladder', 'Metabolism', 'Urogenital',
    'Endocrine', 'Locomotor', 'Blood', 'Cardiovascular', 'Lymph', 'Immune',
]

SENSITIVITY_CATEGORIES = [
    'Grain', 'Additives', 'Addiitives', 'Dairy', 'Environmental', 'Beverages',
    'DairyAlternative', 'Dairy Alternaive', 'Fish', 'Fruit', 'Ingredients',
    'Legume', 'Meat', 'Nut', 'Shellfish', 'Spice', 'Sugar', 'Vegetable',
]

NUTRIENT_GROUPS = [
    'Vitamins', 'Enzymes', 'FattyAcids', 'Fatty Acids', 'Amino Acids',
    'Minerals', 'FayAcids',
]

TOXIN_GROUPS = ['Bacteria', 'Parasites', 'Metals', 'Mold', 'Chemicals', 'Virus']

SECTION_PATTERNS = [
    ('system_performance', r'energ.{0,6}c\s+system\s+performance'),
    ('sensitivities', r'energ.{0,6}c\s+sensiti'),
    ('nutritional', r'energ.{0,6}c\s+nutri'),
    ('toxins', r'energ.{0,6}c\s+t\s*oxins'),
    ('hormonal', r'energ.{0,6}c\s+hormonal\s+imbalances'),
    ('metabolic', r'metabolic\s+test\s+results'),
    ('sleep', r'better\s+sleep\s+scan\s+results'),
    ('hormone_test', r'hormone\s+test\s+results'),
    ('summary', r'personalized\s+client\s+summary'),
    ('next_steps', r'next\s+steps'),
    ('remedies', r'balancing\s+remedies'),
    ('disclaimer', r'disclaimer'),
]


def _normalize_scan_text(text):
    text = text or ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def _find_sections(raw_text):
    """Split scan text into named sections."""
    text = _normalize_scan_text(raw_text)
    lower = text.lower()
    hits = []
    for key, pattern in SECTION_PATTERNS:
        for match in re.finditer(pattern, lower, re.I):
            hits.append((match.start(), key, match.group(0)))
    hits.sort(key=lambda h: h[0])

    sections = {}
    for idx, (start, key, _label) in enumerate(hits):
        end = hits[idx + 1][0] if idx + 1 < len(hits) else len(text)
        chunk = text[start:end].strip()
        chunk = re.sub(r'^[^\n]+\n', '', chunk, count=1).strip()
        if chunk and key not in sections:
            sections[key] = chunk
        elif chunk:
            sections[key] = sections.get(key, '') + '\n\n' + chunk
    return sections


def _extract_title_info(raw_text, client_name, title):
    text = _normalize_scan_text(raw_text)
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    scan_title = title or 'Full Scan'
    display_name = client_name or 'Client'
    scan_date = datetime.now().strftime('%m/%d/%Y')

    if lines:
        if re.match(r'^full\s+scan', lines[0], re.I):
            scan_title = lines[0]
        if len(lines) > 1:
            date_match = re.search(
                r'(.+?)\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})',
                lines[1],
            )
            if date_match:
                display_name = date_match.group(1).strip()
                scan_date = date_match.group(2).strip()
            elif not client_name:
                display_name = lines[1].split(' - ')[0].strip()

    return scan_title, display_name, scan_date


def _parse_systems(text):
    systems = []
    for name in SYSTEM_NAMES:
        if re.search(rf'\b{re.escape(name)}\b', text, re.I):
            systems.append(name.replace('LiverGallbladder', 'Liver / Gallbladder'))
    notes = ''
    note_match = re.search(
        r'notes\s*(.*?)(?=energetic\s+sensiti|energetic\s+nutri|$)',
        text,
        re.I | re.S,
    )
    if note_match:
        notes = note_match.group(1).strip()
    stressed = re.search(
        r'most\s+signific[^\n]*stressed:\s*([^\n]+)',
        text,
        re.I,
    )
    stressed_line = stressed.group(1).strip() if stressed else ''
    return systems, notes, stressed_line


def _parse_category_columns(text, categories):
    """Parse multi-column category lists (sensitivities, toxins)."""
    groups = {cat: [] for cat in categories}
    current = None
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.lower() == 'none':
            if current:
                continue
            continue
        matched_cat = None
        for cat in categories:
            if re.match(rf'^{re.escape(cat)}\b', line, re.I):
                matched_cat = cat
                break
        if matched_cat:
            current = matched_cat
            remainder = line[len(matched_cat):].strip()
            if remainder and remainder.lower() != 'none':
                groups[current].append(remainder)
            continue
        if current and line.lower() != 'none':
            groups[current].append(line)
    return {k: v for k, v in groups.items() if v}


def _parse_nutrient_groups(text):
    groups = {}
    current = None
    buffer = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        group_hit = None
        for grp in NUTRIENT_GROUPS:
            if re.match(rf'^{re.escape(grp)}\b', line, re.I):
                group_hit = grp
                break
        if group_hit:
            if current and buffer:
                groups[current] = '\n'.join(buffer).strip()
            current = group_hit.replace('FayAcids', 'Fatty Acids')
            buffer = []
            rest = line[len(group_hit):].strip()
            if rest:
                buffer.append(rest)
            continue
        if current:
            buffer.append(line)
    if current and buffer:
        groups[current] = '\n'.join(buffer).strip()
    return groups


def _parse_hormone_items(text):
    items = []
    for match in re.finditer(
        r'(Low|High)\s+([A-Za-z0-9\-\(\) /]+)\n(.*?)(?=\n(?:Low|High)\s+[A-Za-z]|\nNotes|\nMETABOLIC|\nBETTER|\nHORMONE|\nPERSONALIZED|\nYOU TESTED WITH|\Z)',
        text,
        re.S,
    ):
        items.append({
            'level': match.group(1),
            'name': match.group(2).strip(),
            'description': _clean_readable_text(match.group(3).strip()),
        })
    if not items:
        for line in text.split('\n'):
            m = re.match(r'^(Low|High)\s+(.+)$', line.strip())
            if m:
                items.append({
                    'level': m.group(1),
                    'name': m.group(2).strip(),
                    'description': '',
                })
    return items


def _extract_hormone_block(scan_text, sections):
    """Hormone lists sometimes appear inside the metabolic section of vendor PDFs."""
    hormonal = sections.get('hormonal', '')
    if hormonal and hormonal.strip().lower() not in ('notes', ''):
        return hormonal
    metabolic = sections.get('metabolic', '')
    match = re.search(
        r'(?:hormones?\s+detected|listed below\.)\s*(.*?)(?=YOU TESTED WITH|\Z)',
        metabolic,
        re.I | re.S,
    )
    if match:
        return match.group(1).strip()
    return hormonal


def _parse_imbalance_cards(text):
    cards = []
    pattern = re.compile(
        r'YOU TESTED WITH\s+(?:AN IMBALANCE IN(?: YOUR)?:?|WITH:?|STRESS IN:?|SUPPORT IN:?)\s*(.+?)\n'
        r'(.*?)(?=YOU TESTED WITH\s+|\Z)',
        re.I | re.S,
    )
    for match in pattern.finditer(text):
        name = match.group(1).strip().rstrip(':')
        body = match.group(2).strip()
        what_is = _extract_arrow_field(body, 'what it is')
        what_means = _extract_arrow_field(body, 'what this means')
        hacks = _extract_arrow_field(body, 'lifestyle hacks') or _extract_arrow_field(
            body, 'to balance naturally'
        )
        cards.append({
            'name': name,
            'what_is': what_is,
            'what_means': what_means,
            'hacks': hacks,
        })
    return cards


def _extract_arrow_field(body, label):
    pattern = rf'→\s*{re.escape(label)}[:\s]*(.*?)(?=→\s*\w|\Z)'
    match = re.search(pattern, body, re.I | re.S)
    return match.group(1).strip() if match else ''


def _parse_remedies(text):
    remedies = []
    split = re.split(r'\nBalancing Remedies\s*\n', text, flags=re.I)
    text = split[-1] if split else text
    text = re.sub(r'^Balancing Remedies\s*', '', text, flags=re.I).strip()
    current_category = ''
    buffer = []
    price = ''

    def flush_product(name_lines):
        nonlocal price, current_category, buffer
        if not name_lines:
            return
        name = name_lines[0][:140]
        details = _clean_readable_text('\n'.join(name_lines[1:] + buffer).strip())
        remedies.append({
            'category': current_category,
            'name': name,
            'details': details,
            'price': price,
        })
        buffer = []
        price = ''

    pending_name = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if re.match(r'^(Homeopathic|Nutri.{0,4}nal\s*Supplements?|Nutritional)$', line, re.I):
            if pending_name:
                flush_product(pending_name)
                pending_name = []
            current_category = re.sub(r'\s+', ' ', line)
            continue
        price_match = re.match(r'^\$(\d+\.\d{2})$', line)
        if price_match:
            price = f'${price_match.group(1)}'
            if pending_name:
                flush_product(pending_name)
                pending_name = []
            continue
        if re.search(r'\$\d+\.\d{2}', line) and not pending_name:
            m = re.search(r'\$(\d+\.\d{2})', line)
            price = f'${m.group(1)}' if m else ''
            line = re.sub(r'\$\d+\.\d{2}', '', line).strip()
            if line:
                pending_name = [line]
            continue
        if not pending_name and len(line) > 4 and not line.startswith('→'):
            if buffer or price:
                flush_product(pending_name or ['Remedy'])
                pending_name = []
            pending_name = [line]
        else:
            buffer.append(line)

    if pending_name:
        flush_product(pending_name)

    remedies = [
        r for r in remedies
        if r.get('name')
        and 'potential remedies including' not in r['name'].lower()
        and (r.get('price') or r.get('details'))
    ]

    if not remedies:
        blocks = re.split(r'\n(?=[A-Z][^\n]{8,}\n)', text)
        for block in blocks:
            lines = [ln.strip() for ln in block.split('\n') if ln.strip()]
            if len(lines) < 2:
                continue
            price_match = re.search(r'\$(\d+\.\d{2})', block)
            remedies.append({
                'category': '',
                'name': lines[0][:120],
                'details': _clean_readable_text('\n'.join(lines[1:])),
                'price': f'${price_match.group(1)}' if price_match else '',
            })
    return remedies[:12]


def _render_columns(groups, columns=4):
    if not groups:
        return ''
    html = '<div class="scan-columns">'
    for cat, items in groups.items():
        if isinstance(items, str):
            body = f'<p class="scan-nutrient-block">{escape(items)}</p>'
        else:
            lis = ''.join(f'<li>{escape(i)}</li>' for i in items)
            body = f'<ul class="scan-list">{lis}</ul>' if lis else '<p class="scan-muted">None</p>'
        html += (
            f'<div class="scan-col">'
            f'<h4>{escape(cat)}</h4>{body}</div>'
        )
    html += '</div>'
    return html


def _render_imbalance_cards(cards):
    if not cards:
        return ''
    parts = []
    for card in cards:
        parts.append(
            f'<div class="scan-imbalance-card">'
            f'<h4>YOU TESTED WITH AN IMBALANCE IN: {escape(card["name"])}</h4>'
            + (f'<p><strong>→ What it is:</strong> {escape(card["what_is"])}</p>' if card['what_is'] else '')
            + (f'<p><strong>→ What this means:</strong> {escape(card["what_means"])}</p>' if card['what_means'] else '')
            + (f'<p><strong>→ Lifestyle support:</strong> {escape(card["hacks"])}</p>' if card['hacks'] else '')
            + '</div>'
        )
    return ''.join(parts)


def _render_hormones(items):
    if not items:
        return ''
    parts = []
    for item in items:
        parts.append(
            f'<div class="scan-hormone-item">'
            f'<h4>{escape(item["level"])} {escape(item["name"])}</h4>'
            + (f'<p>{escape(item["description"])}</p>' if item['description'] else '')
            + '</div>'
        )
    return ''.join(parts)


def _scan_body_text(raw_text):
    """Strip admin PDF wrappers so detection runs on scan content only."""
    text = raw_text or ''
    if '--- SCAN PDF:' not in text:
        return text
    chunks = []
    for block in re.split(r'---\s*SCAN PDF:[^\n]*---\s*', text, flags=re.I):
        block = block.strip()
        if block and not block.startswith('[PDF uploaded:'):
            chunks.append(block)
    return '\n\n'.join(chunks) if chunks else text


def uses_template_format(raw_text, title=None):
    body = _scan_body_text(raw_text)
    lower = body.lower()
    if re.match(r'^full\s+scan\b', lower.strip()):
        return True
    if title and 'full scan' in title.lower() and len(body.strip()) >= 200:
        return True
    if _find_sections(body):
        return True
    markers = (
        'system performance',
        'metabolic test results',
        'balancing remedies',
        'better sleep scan',
        'hormone test results',
        'energetic sensiti',
        'energetic nutri',
        'energetic toxins',
        'energetic hormonal',
        'you tested with',
        'personalized client summary',
    )
    return sum(1 for m in markers if m in lower) >= 2


def generate_template_report_html(
    email, title, raw_data, client_name=None, ai_recommendations_html=None,
):
    """Build HTML report styled like the Full Scan PDF template."""
    scan_text = _scan_body_text(raw_data)
    sections = _find_sections(scan_text)
    scan_title, display_name, scan_date = _extract_title_info(
        scan_text, client_name, title
    )

    sys_text = sections.get('system_performance', '')
    if not sys_text:
        first_section = re.search(r'energ.{0,6}c\s+sensiti', scan_text, re.I)
        sys_text = scan_text[:first_section.start()] if first_section else scan_text[:4000]
    systems, sys_notes, stressed = _parse_systems(sys_text)
    sensitivities = _parse_category_columns(
        sections.get('sensitivities', ''), SENSITIVITY_CATEGORIES
    )
    nutrients = _parse_nutrient_groups(sections.get('nutritional', ''))
    toxins = _parse_category_columns(sections.get('toxins', ''), TOXIN_GROUPS)
    hormones = _parse_hormone_items(_extract_hormone_block(scan_text, sections))
    metabolic_cards = _parse_imbalance_cards(sections.get('metabolic', ''))
    sleep_cards = _parse_imbalance_cards(sections.get('sleep', ''))
    hormone_cards = _parse_imbalance_cards(sections.get('hormone_test', ''))
    remedies = _parse_remedies(sections.get('remedies', ''))

    systems_html = ''.join(
        f'<span class="scan-system-pill">{escape(s)}</span>' for s in systems
    ) or '<p class="scan-muted">See scan data for system performance details.</p>'

    intro_metabolic = _section_intro(sections.get('metabolic', ''), 'metabolic')
    intro_sleep = _section_intro(sections.get('sleep', ''), 'sleep')
    intro_hormone = _section_intro(sections.get('hormone_test', ''), 'hormone')

    summary_text = _clean_readable_text(sections.get('summary', '').strip())
    next_steps = _clean_readable_text(sections.get('next_steps', '').strip())
    disclaimer = sections.get('disclaimer', '').strip()

    remedies_html = ''
    last_category = None
    for rem in remedies:
        if rem.get('category') and rem['category'] != last_category:
            remedies_html += f'<h3 class="scan-remedy-category">{escape(rem["category"])}</h3>'
            last_category = rem['category']
        remedies_html += (
            f'<div class="scan-remedy-card">'
            f'<h4>{escape(rem["name"])}</h4>'
            + (f'<p>{escape(rem["details"][:1200])}</p>' if rem.get("details") else '')
            + (f'<p class="scan-price">{escape(rem["price"])}</p>' if rem.get("price") else '')
            + '</div>'
        )

    raw_fallback = ''
    if not sections and scan_text.strip():
        raw_fallback = (
            '<section class="scan-section">'
            '<h3>Scan Data</h3>'
            f'<pre class="scan-raw-fallback">{escape(scan_text[:15000])}</pre>'
            '</section>'
        )

    return f"""<article class="scan-report">
  <header class="scan-cover">
    <p class="scan-brand">Root Cause Bioenergetics</p>
    <h1 class="scan-main-title">{escape(scan_title)}</h1>
    <p class="scan-client-line">{escape(display_name)} — {escape(scan_date)}</p>
    <p class="scan-client-email">{escape(email)}</p>
  </header>

  <section class="scan-section page-break">
    <h2>Energetic System Performance</h2>
    <p class="scan-lead">The goal is to eventually have each system at 100%. We scan 58 points to create the system performance chart below.</p>
    <div class="scan-legend">
      <span>100%: Minor Stress</span>
      <span>80%: Stress</span>
      <span>60%: Chronic Stress</span>
      <span>40%: Weakness</span>
      <span>20%: Chronic Weakness</span>
    </div>
    <div class="scan-systems-grid">{systems_html}</div>
    {f'<div class="scan-notes"><h4>Notes</h4><p><strong>Most significantly stressed:</strong> {escape(stressed)}</p><p>{escape(sys_notes[:2000])}</p></div>' if stressed or sys_notes else ''}
  </section>

  {f'<section class="scan-section page-break"><h2>Energetic Sensitivities</h2><p class="scan-lead">Items that came up bioenergetically sensitive. With time as the body rebalances, some of these may change.</p>{_render_columns(sensitivities)}</section>' if sensitivities else ''}

  {f'<section class="scan-section page-break"><h2>Energetic Nutritional Imbalances</h2><p class="scan-lead">Nutrients that are bioenergetically low — enzymes, fatty acids, vitamins, minerals, and amino acids.</p>{_render_columns(nutrients)}</section>' if nutrients else ''}

  {f'<section class="scan-section page-break"><h2>Energetic Toxins</h2><p class="scan-lead">Resonating heavy metals, bacteria, viruses, molds, parasites, and chemicals detected in the bioenergetic scan.</p>{_render_columns(toxins)}</section>' if toxins else ''}

  {f'<section class="scan-section page-break"><h2>Energetic Hormonal Imbalances</h2><p class="scan-lead">Hormones detected as resonating imbalances during your scan.</p>{_render_hormones(hormones)}</section>' if hormones else ''}

  {f'<section class="scan-section page-break"><h2>Metabolic Test Results</h2>{intro_metabolic}{_render_imbalance_cards(metabolic_cards)}</section>' if metabolic_cards or intro_metabolic else ''}

  {f'<section class="scan-section page-break"><h2>Better Sleep Scan Results</h2>{intro_sleep}{_render_imbalance_cards(sleep_cards)}</section>' if sleep_cards or intro_sleep else ''}

  {f'<section class="scan-section page-break"><h2>Hormone Test Results</h2>{intro_hormone}{_render_imbalance_cards(hormone_cards)}</section>' if hormone_cards or intro_hormone else ''}

  {f'<section class="scan-section page-break"><h2>Personalized Client Summary</h2><p class="scan-lead">Your results explained in plain language — what stands out and what it means for how you feel day to day.</p><div class="scan-summary scan-prose"><p>{_format_paragraphs(summary_text)}</p></div></section>' if summary_text else ''}

  {f'<section class="scan-section"><h2>Next Steps</h2><p class="scan-lead">A simple action plan to support your body as it rebalances.</p>{_format_next_steps_html(next_steps)}</section>' if next_steps else ''}

  {f'<section class="scan-section page-break"><h2>Balancing Remedies</h2><p class="scan-lead">Remedies identified to bring energetic stressors back into balance — herbs, homeopathics, and nutritional supplements.</p>{remedies_html}</section>' if remedies_html else ''}

  {ai_recommendations_html or ''}

  {raw_fallback}

  <footer class="scan-disclaimer">
    <p>{escape(disclaimer) if disclaimer else 'These statements have not been evaluated by the Food and Drug Administration. This service is for educational purposes only and is not intended to diagnose, treat, cure, or prevent any disease.'}</p>
    <p>Root Cause Bioenergetics • Generated {datetime.now().strftime('%B %d, %Y')}</p>
  </footer>
</article>"""


def _section_intro(text, kind):
    if not text:
        return ''
    intro = text.split('YOU TESTED WITH', 1)[0].strip()
    intro = re.sub(r'^HORMONE TEST RESULTS.*?\n', '', intro, flags=re.I)
    intro = re.sub(r'^METABOLIC TEST RESULTS:?\s*', '', intro, flags=re.I)
    intro = re.sub(r'^BETTER SLEEP SCAN RESULTS\s*', '', intro, flags=re.I)
    if len(intro) < 40:
        return ''
    return f'<div class="scan-section-intro"><p>{_format_paragraphs(intro)}</p></div>'


def _clean_readable_text(text):
    """Normalize OCR quirks so scan copy reads naturally."""
    if not text:
        return ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'→\s*', '→ ', text)
    text = re.sub(r'([a-z])([A-Z][a-z]{3,})', r'\1 \2', text)
    text = re.sub(r'([a-z])(Androstenedione|Lipoprotein|Alpha|Beta)', r'\1 \2', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' ?\n ?', '\n', text)
    return text.strip()


def _format_paragraphs(text):
    if not text:
        return ''
    text = _clean_readable_text(text)
    text = re.sub(
        r'^(PERSONALIZED CLIENT SUMMARY|NEXT STEPS|SUMMARY)[:\s]*',
        '',
        text,
        flags=re.I,
    )
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if len(paras) <= 1 and len(text) > 280:
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'])', text)
        paras = []
        chunk = []
        for sentence in sentences:
            chunk.append(sentence.strip())
            if len(chunk) >= 3:
                paras.append(' '.join(chunk))
                chunk = []
        if chunk:
            paras.append(' '.join(chunk))
    if not paras:
        paras = [ln.strip() for ln in text.split('\n') if ln.strip()]
    return '</p><p>'.join(escape(p) for p in paras)


def _format_next_steps_html(text):
    if not text:
        return ''
    text = _clean_readable_text(text)
    text = re.sub(r'^Next Steps[:\s]*', '', text, flags=re.I).strip()
    text = re.sub(r'Disclaimer:.*', '', text, flags=re.I | re.S).strip()
    steps = []
    parts = re.split(r'(?=\d+\.\s+)', text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.match(r'^\d+\.\s*(.+)$', part, re.S)
        if not match:
            continue
        step = re.sub(r'\s+', ' ', match.group(1).strip())
        if step:
            steps.append(step)
    if steps:
        items = ''.join(f'<li>{escape(s)}</li>' for s in steps)
        return f'<ol class="scan-steps">{items}</ol>'
    return f'<div class="scan-summary"><p>{_format_paragraphs(text)}</p></div>'