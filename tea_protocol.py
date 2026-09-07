"""Tea recommendations mapped to scan categories. Food-level only."""
from html import escape


TEA_MAP = {
    'Digestive & Gut': [
        'Ginger tea after meals to ease sluggish digestion',
        'Chamomile in the evening to calm an irritated gut',
        'Marshmallow root or slippery elm as a cold infusion if the lining feels raw',
    ],
    'Immune & Microbial': [
        'Pau d’arco tea 1–2 cups daily for 4–6 weeks, then reassess',
        'Thyme or green tea for everyday microbial and antioxidant support',
        'Oregano leaf tea only as a short course (1–2 weeks), not all year',
    ],
    'Nervous & Stress': [
        'Lemon balm tea in the late afternoon',
        'Chamomile + lavender in the evening',
        'Tulsi (holy basil) earlier in the day if fatigue is the main issue',
    ],
    'Hormonal & Endocrine': [
        'Ginger or spearmint with meals',
        'Keep thyroid medicine 4 hours away from tea and minerals',
        'Do not add kelp or high-iodine tea unless a clinician cleared it',
    ],
    'Nutritional & Metabolic': [
        'Green tea in the morning if you tolerate caffeine',
        'Cinnamon-ginger tea with meals for a steadier blood-sugar feel',
    ],
    'Detox & Elimination': [
        'Dandelion root tea in the morning',
        'Rooibos or milk thistle seed tea as a gentle daily liver tea',
        'Nettle leaf or corn silk only in the daytime if puffiness is an issue',
    ],
    'Structural & Circulatory': [
        'Green tea or hibiscus in the morning (hibiscus can lower blood pressure)',
        'Turmeric-ginger tea if joints feel inflamed',
    ],
    'General Findings': [
        'Ginger in the morning and chamomile at night as a simple foundation',
    ],
}

FOUNDATION = [
    'Morning: ginger tea, or green tea if you handle caffeine',
    'Evening: chamomile + lemon balm (caffeine-free)',
]

CAUTIONS = [
    'Pregnancy or trying to conceive: skip pau d’arco, oregano, whole licorice, and large amounts of hibiscus.',
    'High blood pressure or heart medicine: skip whole licorice; go easy on hibiscus.',
    'Reflux: skip peppermint; use ginger or slippery elm instead.',
    'Blood thinners: large daily doses of ginger, turmeric, or green tea need a clinician\'s OK.',
    'Pause strong herbal teas 3 days before a follow-up hair scan if you want a cleaner retest.',
]


def teas_for_categories(categories):
    seen = set()
    items = []
    for cat in categories or []:
        for line in TEA_MAP.get(cat, []):
            if line not in seen:
                seen.add(line)
                items.append(line)
        if len(items) >= 4:
            break
    if not items:
        items = list(FOUNDATION)
    return FOUNDATION[:2] + items[:4]


def tea_list_html(categories):
    items = teas_for_categories(categories)
    lis = ''.join(f'<li>{escape(item)}</li>' for item in items)
    caution = ''.join(f'<li>{escape(c)}</li>' for c in CAUTIONS[:3])
    return (
        '<h4>Teas to Drink</h4>'
        f'<ul>{lis}</ul>'
        '<p class="rec-note">Brew leaf teas 5–10 minutes covered. Simmer roots 10–15 minutes. '
        'Cold-steep marshmallow or slippery elm 4+ hours. 2–3 cups a day unless cautions apply.</p>'
        f'<ul>{caution}</ul>'
    )
