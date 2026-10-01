"""Client-facing analysis blocks. Never print raw scan coefficients."""
import re
from html import escape


def sanitize_client_html(html):
    html = html or ''
    parts = re.split(r'(<[^>]+>)', html)
    out = []
    for part in parts:
        if part.startswith('<') and part.endswith('>'):
            out.append(part)
            continue
        part = re.sub(r'\bD\s*=\s*[-+]?\d+(?:\.\d+)?', '', part)
        part = re.sub(r'\bE\s*=\s*[-+]?\d+(?:\.\d+)?', '', part)
        part = re.sub(r'\b\d{1,3}\s*%', '', part)
        part = re.sub(r'\bentropy\s*[:=]\s*[-+]?\d+(?:\.\d+)?', '', part, flags=re.I)
        out.append(part)
    return ''.join(out)


def _categories_from_text(raw):
    text = (raw or '').lower()
    cats = []
    mapping = [
        ('Digestive & Gut', ('digest', 'intestin', 'gut', 'stomach', 'candida', 'pylori', 'colon')),
        ('Immune & Microbial', ('immune', 'virus', 'bacter', 'fung', 'yeast', 'parasite')),
        ('Hormonal & Endocrine', ('hormon', 'thyroid', 'estrogen', 'progesterone', 'cortisol', 'adrenal')),
        ('Nervous & Stress', ('nervous', 'stress', 'anxiety', 'sleep', 'insomnia')),
        ('Nutritional & Metabolic', ('vitamin', 'mineral', 'metabol', 'glucose', 'insulin')),
        ('Detox & Elimination', ('liver', 'kidney', 'toxin', 'detox')),
    ]
    for cat, keys in mapping:
        if any(k in text for k in keys):
            cats.append(cat)
    return cats or ['General Findings']


def analysis_blocks_html(raw_data, client_name='Client', medical_text=''):
    first = escape((client_name or 'Client').split()[0])
    raw = raw_data or ''
    cats = _categories_from_text(raw + '\n' + (medical_text or ''))
    try:
        from tea_protocol import tea_list_html
        tea_html = '<section id="tea-protocol"><h3>Teas to Take</h3>' + tea_list_html(cats) + '</section>'
    except Exception:
        tea_html = '<section id="tea-protocol"><h3>Teas to Take</h3><ul><li>Morning: ginger tea</li><li>Evening: chamomile</li></ul></section>'
    lab_rows = [
        ('CBC + CMP + A1C + lipids', 'Baseline blood count, liver/kidney, sugar, cholesterol'),
        ('hs-CRP + vitamin D 25-OH + B12 + ferritin + TSH', 'Inflammation, nutrient and thyroid screen'),
    ]
    if 'Digestive & Gut' in cats:
        lab_rows.append(('H. pylori stool antigen + GI-MAP or GI Effects', 'Gut follow-up when insurance or cash allows'))
    labs = ''.join('<li><strong>%s</strong> — %s</li>' % (escape(n), escape(w)) for n, w in lab_rows)
    lab_html = (
        '<section id="recommended-labs"><h3>Blood Tests and Where to Get Them</h3><ul>'
        + labs +
        '</ul><p><strong>Insurance / One Medical:</strong> have your clinician order the panel at Quest or LabCorp.</p>'
        '<p><strong>Cheapest cash pay:</strong> <a href="https://www.ultalabtests.com/" target="_blank" rel="noopener">Ulta Lab Tests</a> '
        'and <a href="https://www.walkinlab.com/" target="_blank" rel="noopener">Walk-In Lab</a>. Basic CBC+CMP is often $30–$80.</p></section>'
    )
    try:
        from affiliate_links import supplement_list_html
        names = ['Magnesium glycinate', 'Vitamin D3 + K2', 'Omega-3 fish oil']
        if 'Digestive & Gut' in cats:
            names = ['Saccharomyces boulardii', 'Berberine', 'Caprylic acid'] + names
        supp_html = '<section id="supplement-plan"><h3>Supplements for Maximum Benefit</h3>' + supplement_list_html(names) + '<p>Links go to Amazon. Start one product at a time.</p></section>'
    except Exception:
        supp_html = '<section id="supplement-plan"><h3>Supplements for Maximum Benefit</h3><ul><li>Magnesium glycinate</li><li>Vitamin D3 + K2</li><li>Omega-3</li></ul></section>'
    return (
        '<div class="client-wellness-plan" id="client-wellness-plan"><h2>What to do next</h2>'
        '<p>' + first + ', these supports come after the findings. They are ideas to discuss, not a prescription. Raw scanner names stay with your practitioner.</p>'
        + tea_html + lab_html + supp_html
        + '<p>Wellness education only — not a diagnosis or a prescription.</p></div>'
    )


def ensure_client_analysis(html, raw_data, client_name='Client', medical_text=''):
    html = sanitize_client_html(html or '')
    blocks = analysis_blocks_html(raw_data, client_name=client_name, medical_text=medical_text)
    if 'id="client-wellness-plan"' in html:
        html = re.sub(r'<div class="client-wellness-plan"[\s\S]*?</div>\s*', blocks, html, count=1)
        return sanitize_client_html(html)
    m = re.search(r'<body[^>]*>', html, re.I)
    if m:
        return sanitize_client_html(html[:m.end()] + blocks + html[m.end():])
    return sanitize_client_html(blocks + html)
