"""Amazon affiliate and lab test links for supplement and blood test recommendations."""
import os
import re
from html import escape
from urllib.parse import quote_plus

AMAZON_TAG = os.environ.get('AMAZON_ASSOCIATE_TAG', 'rootcause08-20')

# Curated low-price Amazon products with Associates commission (ASINs)
SUPPLEMENT_PRODUCTS = [
    {
        'keywords': ['digestive enzyme', 'enzyme complex', 'enzymes'],
        'label': 'Digestive Enzymes (NOW Super Enzymes)',
        'asin': 'B0001TNCKQ',
        'search': 'NOW Super Enzymes capsules',
    },
    {
        'keywords': ['probiotic', 'probiotics', 'broad-spectrum probiotic'],
        'label': 'Probiotics (Garden of Life Dr. Formulated)',
        'asin': 'B00D82S5Y0',
        'search': 'Garden of Life probiotic 30 billion',
    },
    {
        'keywords': ['magnesium glycinate', 'magnesium'],
        'label': 'Magnesium Glycinate (Doctor\'s Best)',
        'asin': 'B000BD0RT0',
        'search': 'Doctors Best magnesium glycinate',
    },
    {
        'keywords': ['zinc', 'zinc picolinate'],
        'label': 'Zinc Picolinate (NOW Foods)',
        'asin': 'B0013OQLGE',
        'search': 'NOW zinc picolinate 50mg',
    },
    {
        'keywords': ['omega-3', 'omega 3', 'fish oil', 'fatty acid'],
        'label': 'Omega-3 Fish Oil (Nordic Naturals)',
        'asin': 'B002CQU564',
        'search': 'Nordic Naturals ultimate omega',
    },
    {
        'keywords': ['vitamin d', 'd3', 'vitamin d3'],
        'label': 'Vitamin D3 + K2 (Sports Research)',
        'asin': 'B00DL3PJAG',
        'search': 'Sports Research vitamin D3 K2',
    },
    {
        'keywords': ['milk thistle', 'liver support', 'silymarin'],
        'label': 'Milk Thistle / Liver Support (Jarrow)',
        'asin': 'B0013OVY8Y',
        'search': 'Jarrow milk thistle',
    },
    {
        'keywords': ['nac', 'n-acetylcysteine', 'n acetyl'],
        'label': 'NAC (NOW Foods N-Acetyl Cysteine)',
        'asin': 'B0019LWVLA',
        'search': 'NOW NAC 600mg',
    },
    {
        'keywords': ['b-complex', 'b complex', 'methylfolate', 'b12', 'folate'],
        'label': 'B-Complex with Methylfolate (Jarrow B-Right)',
        'asin': 'B00120JT0S',
        'search': 'Jarrow B-Right complex',
    },
    {
        'keywords': ['glutamine', 'l-glutamine', 'gut lining'],
        'label': 'L-Glutamine (NOW Foods Powder)',
        'asin': 'B000F4SF0K',
        'search': 'NOW L-Glutamine powder',
    },
    {
        'keywords': ['multivitamin', 'multi vitamin', 'multimineral'],
        'label': 'Multivitamin (Nature Made Multi)',
        'asin': 'B004QQ9LRO',
        'search': 'Nature Made multivitamin adults',
    },
    {
        'keywords': ['coq10', 'co q10', 'mitochondrial', 'ubiquinol'],
        'label': 'CoQ10 (Qunol Ultra CoQ10)',
        'asin': 'B0055OUOQQ',
        'search': 'Qunol CoQ10 100mg',
    },
    {
        'keywords': ['adaptogen', 'adrenal', 'ashwagandha'],
        'label': 'Adaptogen Support (Ashwagandha - Nutricost)',
        'asin': 'B01N9K7ZQS',
        'search': 'Nutricost ashwagandha KSM-66',
    },
    {
        'keywords': ['selenium', 'iodine', 'thyroid'],
        'label': 'Selenium (NOW Foods 200mcg)',
        'asin': 'B0013OQGD6',
        'search': 'NOW selenium 200mcg',
    },
    {
        'keywords': ['immune', 'mushroom', 'antimicrobial', 'botanical'],
        'label': 'Immune Mushroom Blend (Host Defense)',
        'asin': 'B002WJ6Q8Y',
        'search': 'Host Defense mycommunity mushrooms',
    },
]

LAB_PROVIDERS = [
    {
        'keywords': [
            'comprehensive metabolic', 'cmp', 'metabolic panel', 'cbc',
            'complete blood', 'blood panel', 'vitamin d', 'ferritin', 'zinc',
            'b12', 'folate', 'thyroid', 'tsh', 'lipid', 'cholesterol',
            'inflammatory', 'crp', 'hs-crp', 'ggt', 'alt', 'ast', 'liver panel',
            'hormone', 'cortisol', 'sex hormone', 'testosterone', 'estrogen',
        ],
        'label': 'Any Lab Test Now',
        'url': 'https://www.anylabtestnow.com/',
        'note': 'Walk-in, no doctor order — compare local pricing',
    },
    {
        'keywords': [
            'stool', 'calprotectin', 'fecal', 'gi map', 'comprehensive stool',
            'parasite', 'microbiome', 'sibo',
        ],
        'label': 'Walk-In Lab (Stool & GI Panels)',
        'url': 'https://www.walkinlab.com/products/view/complete-stool-analysis',
        'note': 'Online order, often lowest price for specialty panels',
    },
    {
        'keywords': [
            'thyroid', 'tsh', 'free t3', 'free t4', 'antibod', 'hormone panel',
        ],
        'label': 'Ulta Lab Tests — Thyroid Panel',
        'url': 'https://www.ultalabtests.com/thyroid-panel',
        'note': 'No insurance needed, online discounted pricing',
    },
    {
        'keywords': [
            'food sensitivity', 'igg', 'allergy', 'sensitivity panel',
        ],
        'label': 'Walk-In Lab — Food Sensitivity',
        'url': 'https://www.walkinlab.com/food-sensitivity-tests',
        'note': 'Compare IgG panels online',
    },
    {
        'keywords': [
            'organic acids', 'oat', 'neurotransmitter', 'mycotoxin', 'mold',
        ],
        'label': 'Any Lab Test Now — Specialty Testing',
        'url': 'https://www.anylabtestnow.com/test-menu/',
        'note': 'Search specialty metabolite panels',
    },
    {
        'keywords': [
            'heavy metal', 'mercury', 'lead', 'toxin', 'detox',
        ],
        'label': 'Walk-In Lab — Heavy Metals',
        'url': 'https://www.walkinlab.com/heavy-metals-tests',
        'note': 'Direct-to-consumer heavy metal screens',
    },
]


def amazon_link(asin=None, search_term=None):
    tag = AMAZON_TAG
    if asin:
        return f'https://www.amazon.com/dp/{asin}?tag={tag}'
    query = quote_plus(search_term or 'supplements')
    return f'https://www.amazon.com/s?k={query}&tag={tag}'


def match_supplement_link(supplement_text):
    """Return (label, url) for a supplement recommendation string."""
    lower = supplement_text.lower()
    for product in SUPPLEMENT_PRODUCTS:
        if any(kw in lower for kw in product['keywords']):
            return product['label'], amazon_link(
                asin=product.get('asin'),
                search_term=product.get('search'),
            )
    return supplement_text, amazon_link(search_term=supplement_text)


def match_lab_links(lab_text):
    """Return list of (provider_label, url, note) matching a lab recommendation."""
    lower = lab_text.lower()
    matches = []
    for provider in LAB_PROVIDERS:
        if any(kw in lower for kw in provider['keywords']):
            matches.append((provider['label'], provider['url'], provider['note']))
    if not matches:
        matches.append((
            'Any Lab Test Now — Search Tests',
            'https://www.anylabtestnow.com/test-menu/',
            'Walk-in labs, no doctor order required',
        ))
        matches.append((
            'Walk-In Lab — Online Ordering',
            'https://www.walkinlab.com/',
            'Often lowest online pricing for blood work',
        ))
    seen = set()
    unique = []
    for label, url, note in matches:
        if url not in seen:
            seen.add(url)
            unique.append((label, url, note))
    return unique[:2]


def supplement_list_html(supplements):
    """Build HTML list with Amazon affiliate links."""
    items = []
    for s in supplements:
        label, url = match_supplement_link(s)
        items.append(
            f'<li><a href="{escape(url)}" target="_blank" rel="noopener sponsored">'
            f'{escape(label)}</a> '
            f'<span class="affiliate-note">— Amazon</span></li>'
        )
    return ''.join(items)


def lab_list_html(labs):
    """Build HTML list with lab provider links."""
    items = []
    for lab in labs:
        providers = match_lab_links(lab)
        provider_links = ' · '.join(
            f'<a href="{escape(url)}" target="_blank" rel="noopener">{escape(label)}</a>'
            for label, url, _note in providers
        )
        items.append(
            f'<li><strong>{escape(lab)}</strong><br>'
            f'<span class="lab-links">{provider_links}</span></li>'
        )
    return ''.join(items)


def enrich_html_with_affiliate_links(html_content):
    """Post-process Grok HTML to add affiliate links to supplement/lab list items."""
    if not html_content:
        return html_content

    def replace_supp_section(match):
        section = match.group(0)
        if 'amazon.com' in section:
            return section
        items = re.findall(r'<li>(.*?)</li>', section, re.DOTALL | re.IGNORECASE)
        if not items:
            return section
        new_items = []
        for item in items:
            plain = re.sub(r'<[^>]+>', '', item).strip()
            if not plain or 'amazon.com' in item:
                new_items.append(f'<li>{item}</li>')
                continue
            label, url = match_supplement_link(plain)
            new_items.append(
                f'<li><a href="{escape(url)}" target="_blank" rel="noopener sponsored">'
                f'{escape(label)}</a> <span class="affiliate-note">— Amazon</span></li>'
            )
        header = re.search(r'<h4[^>]*>.*?Supplement.*?</h4>', section, re.I)
        header_html = header.group(0) if header else '<h4>Suggested Supplements</h4>'
        return f'{header_html}<ul>{"".join(new_items)}</ul>'

    def replace_lab_section(match):
        section = match.group(0)
        if 'anylabtestnow.com' in section or 'walkinlab.com' in section:
            return section
        items = re.findall(r'<li>(.*?)</li>', section, re.DOTALL | re.IGNORECASE)
        if not items:
            return section
        new_items = []
        for item in items:
            plain = re.sub(r'<[^>]+>', '', item).strip()
            if not plain:
                continue
            providers = match_lab_links(plain)
            links = ' · '.join(
                f'<a href="{escape(u)}" target="_blank" rel="noopener">{escape(l)}</a>'
                for l, u, _n in providers
            )
            new_items.append(
                f'<li><strong>{escape(plain)}</strong><br><span class="lab-links">{links}</span></li>'
            )
        header = re.search(r'<h4[^>]*>.*?Lab.*?</h4>', section, re.I)
        header_html = header.group(0) if header else '<h4>Labs to Discuss</h4>'
        return f'{header_html}<ul>{"".join(new_items)}</ul>'

    html = re.sub(
        r'<h4[^>]*>.*?Supplement.*?</h4>\s*<ul>.*?</ul>',
        replace_supp_section,
        html_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r'<h4[^>]*>.*?Lab.*?</h4>\s*<ul>.*?</ul>',
        replace_lab_section,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return html