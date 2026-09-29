"""Whole-food-first scoring (rubric "whole-food-v2").

Processing level is the dominant factor:
  Tier 1  whole / unprocessed (NOVA 1)            -> 90-100
  Tier 1b whole food + kitchen basics only         -> 85-96
  Tier 2  single culinary ingredient (NOVA 2)      -> 25-80
  Tier 3  processed (NOVA 3)                       -> 40-79 (55 max with refined seed oil)
  Tier 4  ultra-processed (NOVA 4 / UPF markers)   -> 1-39, regardless of macros

Macros only nudge a score inside its tier. Natural sugar in whole fruit and
natural fat in nuts, eggs, meat or fish are never penalized. Educational
wellness information only; this is not medical advice.
"""
import re

RUBRIC_VERSION = 'whole-food-v2'

# ---------------------------------------------------------------- vocab
WHOLE_FOODS = (
    # fruit
    'apple', 'apples', 'banana', 'bananas', 'orange', 'oranges', 'mandarin', 'clementine', 'grapefruit', 'lemon', 'lime',
    'grape', 'grapes', 'strawberry', 'strawberries', 'blueberry', 'blueberries', 'raspberry', 'raspberries', 'blackberry',
    'blackberries', 'cherries', 'cherry', 'cranberries', 'peach', 'peaches', 'pear', 'pears', 'plum', 'plums', 'apricot',
    'apricots', 'mango', 'mangoes', 'pineapple', 'papaya', 'kiwi', 'watermelon', 'cantaloupe', 'melon', 'honeydew',
    'pomegranate', 'figs', 'fig', 'dates', 'date', 'raisins', 'prunes', 'avocado', 'avocados', 'coconut', 'olives',
    'berries', 'mixed berries', 'fruit',
    # vegetables
    'spinach', 'kale', 'lettuce', 'romaine', 'arugula', 'cabbage', 'broccoli', 'cauliflower', 'brussels sprouts', 'carrot',
    'carrots', 'celery', 'cucumber', 'cucumbers', 'tomato', 'tomatoes', 'bell pepper', 'peppers', 'pepper', 'onion', 'onions',
    'garlic', 'potato', 'potatoes', 'sweet potato', 'sweet potatoes', 'yam', 'beet', 'beets', 'zucchini', 'squash',
    'butternut squash', 'pumpkin', 'asparagus', 'green beans', 'peas', 'green peas', 'corn', 'sweet corn', 'mushrooms',
    'mushroom', 'eggplant', 'radish', 'turnip', 'leek', 'leeks', 'artichoke', 'okra', 'bok choy', 'chard', 'collard greens',
    'mixed vegetables', 'vegetables', 'salad greens', 'herbs', 'ginger', 'turmeric root',
    # animal
    'egg', 'eggs', 'whole eggs', 'egg whites', 'beef', 'ground beef', 'steak', 'chicken', 'chicken breast', 'chicken thighs',
    'turkey', 'ground turkey', 'pork', 'pork chop', 'lamb', 'bison', 'venison', 'salmon', 'wild salmon', 'tuna', 'cod',
    'halibut', 'tilapia', 'trout', 'sardines', 'mackerel', 'anchovies', 'shrimp', 'scallops', 'mussels', 'oysters', 'clams',
    'crab', 'lobster', 'fish', 'milk', 'whole milk', 'raw milk', 'liver',
    # legumes
    'black beans', 'pinto beans', 'kidney beans', 'navy beans', 'white beans', 'cannellini beans', 'great northern beans',
    'garbanzo beans', 'chickpeas', 'lentils', 'red lentils', 'green lentils', 'split peas', 'edamame', 'soybeans', 'beans',
    'mung beans', 'lima beans', 'black-eyed peas', 'adzuki beans',
    # nuts & seeds
    'almonds', 'walnuts', 'cashews', 'pecans', 'pistachios', 'hazelnuts', 'macadamia nuts', 'brazil nuts', 'peanuts',
    'pine nuts', 'mixed nuts', 'nuts', 'chia seeds', 'flax seeds', 'flaxseed', 'ground flaxseed', 'hemp seeds', 'hemp hearts',
    'pumpkin seeds', 'pepitas', 'sunflower seeds', 'sesame seeds',
    # whole grains
    'oats', 'rolled oats', 'whole grain oats', 'whole grain rolled oats', 'steel cut oats', 'brown rice', 'wild rice',
    'quinoa', 'buckwheat', 'millet', 'barley', 'farro', 'amaranth', 'sorghum', 'teff', 'popcorn kernels', 'rice',
    # other single foods
    'water', 'spring water', 'mineral water', 'sparkling water', 'carbonated water', 'coffee', 'green tea', 'tea',
    'plain yogurt', 'plain greek yogurt',
)
# Items that may appear next to whole foods without leaving "minimally processed".
KITCHEN_BASICS = (
    'salt', 'sea salt', 'kosher salt', 'himalayan salt', 'water', 'filtered water', 'vinegar', 'apple cider vinegar',
    'lemon juice', 'lime juice', 'extra virgin olive oil', 'olive oil', 'avocado oil', 'coconut oil', 'butter', 'ghee',
    'spices', 'spice', 'black pepper', 'herbs', 'garlic', 'onion', 'paprika', 'cumin', 'oregano', 'basil', 'thyme',
    'rosemary', 'parsley', 'cilantro', 'dill', 'cinnamon', 'turmeric', 'ginger', 'chili', 'chili powder', 'cayenne',
    'garlic powder', 'onion powder', 'bay leaf', 'mustard seed', 'nutmeg', 'vanilla bean',
    'vitamin d3',
)
BENIGN_ADDITIVES = (
    'citric acid', 'ascorbic acid', 'vitamin c', 'tocopherols', 'mixed tocopherols', 'vitamin e', 'calcium chloride',
    'pectin', 'baking soda', 'sodium bicarbonate', 'vitamin a palmitate',
    'cultures', 'live cultures', 'live and active cultures', 'live active cultures', 'active cultures', 'yogurt cultures',
    'bacterial cultures', 'probiotic cultures',
)
BENIGN_E = {'e300', 'e301', 'e306', 'e307', 'e308', 'e309', 'e330', 'e440', 'e440i', 'e500', 'e500i', 'e500ii', 'e509', 'e290', 'e170', 'e170i'}
CULINARY_SINGLE = {
    'extra virgin olive oil': 78, 'olive oil': 74, 'avocado oil': 74, 'butter': 72, 'ghee': 72, 'coconut oil': 66,
    'lard': 62, 'tallow': 62, 'honey': 62, 'raw honey': 64, 'maple syrup': 58, 'pure maple syrup': 58, 'sea salt': 60,
    'salt': 60, 'vinegar': 70, 'apple cider vinegar': 72, 'molasses': 50,
    'sugar': 30, 'cane sugar': 30, 'brown sugar': 28, 'corn syrup': 25, 'agave syrup': 40, 'agave': 40,
    'canola oil': 35, 'vegetable oil': 32, 'soybean oil': 32, 'corn oil': 32, 'sunflower oil': 35, 'safflower oil': 35,
    'grapeseed oil': 35, 'cottonseed oil': 30,
}

# (regex, label, weight). High = 10, medium = 6, low = 3.
UPF_MARKERS = (
    (r'\b(aspartame|sucralose|acesulfame(?: potassium| k)?|ace-?k|saccharin|neotame|advantame|cyclamate)\b', 'artificial sweetener', 10),
    (r'\b(red|yellow|blue|green)\s*(no\.?\s*)?\d+\b|\bartificial colou?rs?\b|\btitanium dioxide\b', 'artificial color', 10),
    (r'\b(partially )?hydrogenated\b|\binteresterified\b', 'hydrogenated oil', 10),
    (r'\bsodium nitrite\b|\bsodium nitrate\b|\bpotassium nitrite\b|\bpotassium nitrate\b', 'nitrite/nitrate preservative', 10),
    (r'\bbha\b|\bbht\b|\btbhq\b|\bbutylated hydroxy(anisole|toluene)\b|\bpropyl gallate\b|\bpotassium bromate\b', 'synthetic preservative', 10),
    (r'\bhigh[- ]fructose corn syrup\b|\bhfcs\b', 'high-fructose corn syrup', 10),
    (r'\bcorn syrup( solids)?\b|\bglucose(-fructose)? syrup\b|\binvert sugar\b|\bmaltodextrin\b|\bdextrose\b|\bcrystalline fructose\b', 'refined sweetener/starch', 6),
    (r'\bmodified (food |corn |potato |tapioca )?starch\b', 'modified starch', 6),
    (r'\bmono-? ?(and|&) ?di-?glycerides\b|\bpolysorbate\s*\d*\b|\bsodium stearoyl lactylate\b|\bdatem\b|\bcarboxymethyl ?cellulose\b|\bcellulose gum\b|\bcarrageenan\b|\bpolyglycerol\b', 'emulsifier', 6),
    (r'\bmonosodium glutamate\b|\bmsg\b|\bdisodium (inosinate|guanylate)\b|\bhydrolyzed (vegetable |soy |corn |wheat )?protein\b|\bautolyzed yeast\b', 'flavor enhancer', 6),
    (r'\b(soy|whey|pea|milk|rice) protein (isolate|concentrate)\b|\bprotein isolate\b', 'protein isolate', 6),
    (r'\bcaramel colou?r\b', 'caramel color', 6),
    (r'\bsodium benzoate\b|\bpotassium benzoate\b|\bpotassium sorbate\b|\bcalcium propionate\b|\bsodium propionate\b', 'preservative', 6),
    (r'\bartificial(ly)? flavou?r(s|ed|ing)?\b', 'artificial flavor', 6),
    (r'\bnatural (and artificial )?flavou?r(s|ing)?\b|\bflavou?ring\b', 'natural flavor', 3),
    (r'\b(soy|sunflower)? ?lecithin\b', 'emulsifier (lecithin)', 3),
    (r'\b(xanthan|guar|gellan|locust bean|acacia|tara) gum\b', 'thickener gum', 3),
    (r'\bstevia (leaf )?extract\b|\brebaudioside\b|\breb[- ]a\b|\bmonk fruit extract\b|\berythritol\b|\bsorbitol\b|\bmaltitol\b|\bxylitol\b', 'non-nutritive sweetener', 3),
    (r'\byeast extract\b', 'yeast extract', 3),
)
E_NUMBER_WEIGHTS = {
    # high
    'e102': 10, 'e104': 10, 'e110': 10, 'e122': 10, 'e124': 10, 'e127': 10, 'e129': 10, 'e131': 10, 'e132': 10, 'e133': 10,
    'e171': 10, 'e249': 10, 'e250': 10, 'e251': 10, 'e252': 10, 'e310': 10, 'e319': 10, 'e320': 10, 'e321': 10,
    'e950': 10, 'e951': 10, 'e952': 10, 'e954': 10, 'e955': 10, 'e961': 10, 'e962': 10,
    # medium
    'e150c': 6, 'e150d': 6, 'e211': 6, 'e212': 6, 'e202': 6, 'e282': 6, 'e407': 6, 'e433': 6, 'e466': 6, 'e471': 6,
    'e472e': 6, 'e481': 6, 'e1422': 6, 'e1442': 6, 'e1450': 6, 'e621': 6, 'e627': 6, 'e631': 6, 'e635': 6,
    # low
    'e322': 3, 'e415': 3, 'e412': 3, 'e418': 3, 'e410': 3, 'e414': 3, 'e960': 3, 'e968': 3, 'e420': 3, 'e965': 3,
}
SEED_OIL_RE = re.compile(r'\b(canola|rapeseed|soybean|soy|corn|cottonseed|sunflower|high oleic sunflower|safflower|high oleic safflower|grapeseed|rice bran|vegetable|palm|palm kernel)\s+oils?\b')
ADDED_SUGAR_RE = re.compile(
    r'(?<!no )(?<!without )\b(sugar|cane sugar|organic cane sugar|brown sugar|raw sugar|coconut sugar|cane juice|evaporated cane juice|'
    r'honey|agave( nectar| syrup)?|maple syrup|molasses|rice syrup|brown rice syrup|tapioca syrup|date syrup|syrup|'
    r'dextrose|fructose|glucose|sucrose|fruit juice concentrate|juice concentrate|caramel)\b(?! snap)'
)
REFINED_FLOUR_RE = re.compile(r'\b(enriched (wheat |bleached )?flour|bleached flour|white flour|wheat flour|unbleached (enriched )?(wheat )?flour|all[- ]purpose flour|white rice flour|semolina)\b')
WHOLE_CATEGORY_TAGS = (
    'fresh-vegetables', 'fresh-fruits', 'fruits', 'vegetables', 'eggs', 'nuts', 'seeds', 'legumes', 'pulses', 'dried-legumes',
    'fresh-meats', 'meats', 'fishes', 'seafood', 'whole-grains', 'oat-flakes', 'rolled-oats', 'rices', 'waters',
    'plain-yogurts', 'milks',
)
BAND_TABLE = (
    (85, 'excellent', 'Whole food - excellent', '#0f6b3a'),
    (70, 'good', 'Good choice', '#1b7f4e'),
    (40, 'ok', 'Okay in moderation', '#c9a227'),
    (20, 'poor', 'Ultra-processed - limit', '#d35400'),
    (0, 'avoid', 'Better to skip', '#b03a2e'),
)
TIER_LABEL = {
    '1': 'Whole food (unprocessed)', '1b': 'Minimally processed (whole food + kitchen basics)',
    '2': 'Culinary ingredient', '3': 'Processed', '4': 'Ultra-processed', 'unknown': 'Processing unknown',
}
PLATE_LEVEL_SCORE = {'whole': 100, 'minimal': 92, 'processed': 60, 'ultra': 25}


# ---------------------------------------------------------------- helpers
def _norm(text):
    text = (text or '').lower()
    text = re.sub(r'100%|\bwhole grain\b|\bwhole wheat\b', ' ', text)
    text = re.sub(r'\b(organic|raw|fresh|frozen|dry|dried|whole|natural|pure|unsalted|roasted|dry roasted|plain|wild[- ]caught|grass[- ]fed|pasture[- ]raised|free[- ]range|cage[- ]free|sprouted|shelled|in shell|unsweetened|filtered|cooked|canned|pasteurized|ultra-pasteurized|cultured|nonfat|non-fat|lowfat|low-fat|reduced fat|skim|grade a)\b', ' ', text)
    text = re.sub(r'[^a-z0-9 \-]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def split_ingredients(text):
    """Top-level ingredient list (sub-ingredients in brackets are kept inside their parent)."""
    text = (text or '').strip().strip('.')
    text = re.sub(r'^\s*ingredients?\s*[:\-]\s*', '', text, flags=re.I)
    if not text:
        return []
    out, depth, buf = [], 0, ''
    for ch in text:
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth = max(0, depth - 1)
        if ch in ',;' and depth == 0:
            if buf.strip():
                out.append(buf.strip())
            buf = ''
        else:
            buf += ch
    if buf.strip():
        out.append(buf.strip())
    cleaned = []
    for item in out:
        item = re.sub(r'\b(contains|less than|2% or less of)\b.*?:', '', item, flags=re.I).strip(' .*')
        if item:
            cleaned.append(item)
    return cleaned


def _base_name(item):
    return _norm(re.sub(r'[\(\[].*?[\)\]]', ' ', item))


def _matches(name, vocab):
    if not name:
        return False
    if name in vocab:
        return True
    # allow simple plural/singular and "x beans" style variants
    if name.endswith('s') and name[:-1] in vocab:
        return True
    return (name + 's') in vocab


def _is_benign(name):
    return name in BENIGN_ADDITIVES or bool(re.fullmatch(r'e\d{3}[a-z]?', name) and name in BENIGN_E)


def detect_markers(ingredients_text, additive_tags=()):
    text = (ingredients_text or '').lower()
    hits = {}
    for pattern, label, weight in UPF_MARKERS:
        if re.search(pattern, text):
            hits[label] = max(hits.get(label, 0), weight)
    for tag in additive_tags or ():
        code = str(tag).lower().replace('en:', '').strip()
        m = re.match(r'e\s*(\d{3,4}[a-z]*)', code)
        if not m:
            continue
        code = 'e' + m.group(1)
        if code not in E_NUMBER_WEIGHTS and code not in BENIGN_E:
            code = re.sub(r'(i{1,3}|iv|v|[a-z])$', '', code) or code  # e340iii -> e340
        if code in BENIGN_E:
            continue
        weight = E_NUMBER_WEIGHTS.get(code, 3)
        hits[code.upper()] = max(hits.get(code.upper(), 0), weight)
    return hits


def _num(nutrients, *keys):
    for key in keys:
        val = (nutrients or {}).get(key)
        if val is None:
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return None


def _band(score):
    for floor, band, label, color in BAND_TABLE:
        if score >= floor:
            return band, label, color
    return BAND_TABLE[-1][1:]


def _looks_whole(product):
    name = _norm(product.get('name'))
    cats = ' '.join(str(c) for c in (product.get('categories_tags') or [])) + ' ' + str(product.get('categories') or '')
    cats = cats.lower()
    if _matches(name, WHOLE_FOODS):
        return True
    words = name.split()
    # "Hass avocados", "Large brown eggs", "Organic baby spinach"
    for n in (3, 2, 1):
        if len(words) >= n and _matches(' '.join(words[-n:]), WHOLE_FOODS):
            if not re.search(r'\b(bar|bars|chips|crisps|cookie|cookies|cereal|drink|soda|candy|sauce|dressing|mix|flavored|flavoured|snack|juice|butter|jam|jelly|spread|pie|cake|muffin|nuggets|sticks)\b', name):
                return True
    return any(('en:' + tag) in cats or tag.replace('-', ' ') in cats for tag in ('fresh-vegetables', 'fresh-fruits', 'eggs', 'fresh-meats', 'fishes'))


# ---------------------------------------------------------------- classify
def classify_processing(product):
    """Return (tier, source, details) where tier in '1','1b','2','3','4','unknown'."""
    ingredients_text = product.get('ingredients') or ''
    items = split_ingredients(ingredients_text)
    markers = detect_markers(ingredients_text, product.get('additives') or [])
    nova = product.get('nova')
    try:
        nova = int(nova) if nova not in (None, '') else None
    except (TypeError, ValueError):
        nova = None
    details = {'items': items, 'markers': markers, 'nova': nova, 'unrecognized': [], 'whole': [], 'basics': []}

    if not items:
        if markers:
            return '4', 'additive list', details
        if product.get('whole_food_hint') or _looks_whole(product):
            return '1', 'whole-food name/category', details
        if nova in (1, 2, 3, 4):
            return ('1' if nova == 1 else str(nova)), 'Open Food Facts NOVA', details
        return 'unknown', 'no ingredient list', details

    if markers:
        return '4', 'ingredient markers', details

    lower_all = ingredients_text.lower()
    if SEED_OIL_RE.search(lower_all) or ADDED_SUGAR_RE.search(lower_all) or REFINED_FLOUR_RE.search(lower_all):
        if len(items) == 1:
            return '2', 'single culinary ingredient', details
        return ('4' if nova == 4 else '3'), 'ingredient analysis', details

    for item in items:
        name = _base_name(item)
        if _matches(name, WHOLE_FOODS):
            details['whole'].append(name)
        elif name in KITCHEN_BASICS or _is_benign(name):
            details['basics'].append(name)
        elif name in CULINARY_SINGLE:
            details['basics'].append(name)
        else:
            details['unrecognized'].append(name)

    if len(items) == 1 and not details['whole'] and _base_name(items[0]) in CULINARY_SINGLE:
        return '2', 'single culinary ingredient', details
    if details['whole'] and not details['unrecognized']:
        non_benign_basics = [b for b in details['basics'] if not _is_benign(b) and b not in ('water', 'filtered water')]
        return ('1b' if non_benign_basics else '1'), 'ingredient analysis', details
    if nova == 4:
        return '4', 'Open Food Facts NOVA', details
    if nova == 1 and len(details['unrecognized']) <= 1:
        return '1', 'Open Food Facts NOVA', details
    if nova == 2 and len(items) <= 2:
        return '2', 'Open Food Facts NOVA', details
    return '3', 'ingredient analysis', details


# ---------------------------------------------------------------- personal
def personal_penalty(product, personal_flags, triggers):
    notes, penalty = [], 0
    haystack = ('%s %s %s' % (product.get('ingredients') or '', product.get('name') or '', product.get('categories') or '')).lower()
    for flag in sorted(set(personal_flags or [])):
        spec = (triggers or {}).get(flag)
        if not spec:
            continue
        hits = [w for w in spec['penalize'] if re.search(r'\b' + re.escape(w), haystack)]
        if hits:
            penalty += min(12, 6 * len(hits))
            notes.append(spec['reason'] + ' Found: ' + ', '.join(hits[:4]) + '.')
    return min(24, penalty), notes


# ---------------------------------------------------------------- score
def score_product_v2(product, personal_flags=None, triggers=None):
    product = product or {}
    if product.get('components'):
        return score_plate(product, personal_flags, triggers)
    nutrients = product.get('nutrients') or {}
    tier, source, d = classify_processing(product)
    items, markers = d['items'], d['markers']
    lower_all = (product.get('ingredients') or '').lower()
    name_l = (product.get('name') or '').lower()
    reasons, adj = [], 0
    sugars = _num(nutrients, 'sugars', 'sugar')
    salt = _num(nutrients, 'salt')
    if salt is None and _num(nutrients, 'sodium') is not None:
        salt = _num(nutrients, 'sodium') * 2.5
    fiber = _num(nutrients, 'fiber') or 0
    protein = _num(nutrients, 'protein') or 0
    sat = _num(nutrients, 'sat_fat')
    organic = 'organic' in ' '.join(str(x) for x in (product.get('labels') or [])).lower()
    added_sugar = bool(ADDED_SUGAR_RE.search(lower_all))
    seed_oil = bool(SEED_OIL_RE.search(lower_all))
    refined_flour = bool(REFINED_FLOUR_RE.search(lower_all))
    count_pen = min(12, max(0, len(items) - 5) * 1.5)

    def sugar_pen():
        if not added_sugar:
            return 0
        if sugars is None:
            return 6
        return 18 if sugars >= 22 else 12 if sugars >= 12 else 7 if sugars >= 5 else 4

    if tier == '1':
        base, floor, cap = 100, 90, 100
        reasons.append('Whole, unprocessed food.' if source != 'Open Food Facts NOVA' else 'Unprocessed food (NOVA 1).')
        if re.search(r'\bjuice\b', name_l) and not re.search(r'\b(lemon|lime)\b', name_l):
            base, floor, cap = 72, 60, 80
            reasons.append('Juice: the fiber of the whole fruit is removed.')
        elif re.search(r'\bdried\b', name_l):
            adj -= 4
            reasons.append('Dried fruit is more concentrated than fresh.')
    elif tier == '1b':
        base, floor, cap = 94, 85, 96
        reasons.append('Whole food with only kitchen basics added (%s).' % ', '.join(sorted(set(d['basics']))[:4]))
        if salt is not None and salt >= 1.5:
            adj -= 4
            reasons.append('On the salty side.')
    elif tier == '2':
        key = _base_name(items[0]) if items else _norm(product.get('name'))
        base = CULINARY_SINGLE.get(key, 60)
        floor, cap = 25, 80
        reasons.append('Single culinary ingredient; use in cooking rather than as a food on its own.')
        if base <= 40:
            reasons.append('Refined sugar or refined seed oil.')
    elif tier == '3':
        base, floor, cap = 70, 40, 79
        reasons.append('Processed food with a short list of recognizable ingredients.')
        if seed_oil:
            adj -= 12
            cap = 55
            reasons.append('Made with refined seed/vegetable oil.')
        sp = sugar_pen()
        if sp:
            adj -= sp
            reasons.append('Contains added sugar.')
        if refined_flour:
            adj -= 5
            reasons.append('Refined flour instead of whole grain.')
        if count_pen:
            adj -= count_pen
            reasons.append('%d ingredients.' % len(items))
        if salt is not None and salt >= 1.5:
            adj -= 6
            reasons.append('High salt.')
        if sat is not None and sat >= 10:
            adj -= 3
        if fiber >= 6:
            adj += 3
        if protein >= 10:
            adj += 2
        if organic:
            adj += 2
    elif tier == '4':
        base, floor, cap = 38, 1, 39
        reasons.append('Ultra-processed: contains industrial additives or ingredients.')
        marker_pen = min(26, sum(sorted(markers.values(), reverse=True)[:4]) - (3 if markers else 0))
        adj -= max(0, marker_pen)
        if markers:
            reasons.append('Detected: %s.' % ', '.join(sorted(markers)[:6]))
        adj -= sugar_pen()
        if added_sugar:
            reasons.append('Contains added sugar.')
        if seed_oil:
            adj -= 5
            reasons.append('Made with refined seed/vegetable oil.')
        adj -= count_pen
        if fiber >= 6:
            adj += 2
        if protein >= 10:
            adj += 1
    else:  # unknown
        base, floor, cap = 60, 30, 75
        reasons.append('No ingredient list found, so processing level is a guess. Add a label photo for a better score.')
        sp = 10 if (sugars or 0) >= 22 else 5 if (sugars or 0) >= 12 else 0
        adj -= sp

    core = int(round(max(floor, min(cap, base + adj))))
    ppen, pnotes = personal_penalty(product, personal_flags, triggers)
    final = int(max(1, min(100, core - ppen)))
    band, label, color = _band(final)
    add_pen = sum(markers.values())
    return {
        'score': final, 'band': band, 'label': label, 'color': color,
        'rubric_version': RUBRIC_VERSION,
        'processing_tier': tier, 'processing_label': TIER_LABEL[tier], 'processing_source': source,
        'processing_score': core, 'reasons': reasons[:6],
        'ingredient_count': len(items), 'upf_markers': sorted(markers)[:10],
        'added_sugar': added_sugar, 'seed_oil': seed_oil,
        # legacy keys kept for history/diary/UI compatibility
        'nutrition_score': core, 'additive_score': max(0, 100 - add_pen),
        'personal_score': 100 - ppen, 'organic_bonus': 2 if organic and tier == '3' else 0,
        'additive_hits': sorted(k for k, v in markers.items() if v >= 6)[:8],
        'personal_notes': pnotes, 'personal_flags': sorted(set(personal_flags or [])),
        'nova': product.get('nova'), 'nutriscore': product.get('nutriscore') or '',
    }


def score_plate(product, personal_flags=None, triggers=None):
    """Score a plate photo from vision components: [{name, processing, share, fried}]."""
    comps = [c for c in (product.get('components') or []) if isinstance(c, dict)]
    total, weight, reasons, worst = 0.0, 0.0, [], []
    for c in comps:
        level = str(c.get('processing') or 'processed').lower()
        level = level if level in PLATE_LEVEL_SCORE else 'processed'
        s = PLATE_LEVEL_SCORE[level]
        if c.get('fried'):
            s -= 10
        try:
            share = float(c.get('share') or 0)
        except (TypeError, ValueError):
            share = 0
        share = share if share > 0 else 1.0 / max(1, len(comps))
        total += s * share
        weight += share
        if level in ('processed', 'ultra') or c.get('fried'):
            worst.append('%s (%s%s)' % (c.get('name') or 'item', level, ', fried' if c.get('fried') else ''))
    core = int(round(total / weight)) if weight else 60
    wholes = [c.get('name') for c in comps if str(c.get('processing')).lower() in ('whole', 'minimal')]
    if wholes:
        reasons.append('Whole or minimally processed: %s.' % ', '.join(str(w) for w in wholes[:5]))
    if worst:
        reasons.append('Processed parts: %s.' % ', '.join(worst[:5]))
    reasons.append('Photo estimate: ingredients and oils used are not visible, so treat this as a rough guide.')
    ppen, pnotes = personal_penalty(product, personal_flags, triggers)
    final = int(max(1, min(100, core - ppen)))
    band, label, color = _band(final)
    tier = '1' if core >= 90 else '1b' if core >= 85 else '3' if core >= 40 else '4'
    return {
        'score': final, 'band': band, 'label': label, 'color': color,
        'rubric_version': RUBRIC_VERSION, 'processing_tier': tier, 'processing_label': TIER_LABEL[tier] + ' (plate estimate)',
        'processing_source': 'plate photo components', 'processing_score': core, 'reasons': reasons,
        'ingredient_count': len(comps), 'upf_markers': [], 'added_sugar': False, 'seed_oil': False,
        'nutrition_score': core, 'additive_score': core, 'personal_score': 100 - ppen, 'organic_bonus': 0,
        'additive_hits': [], 'personal_notes': pnotes, 'personal_flags': sorted(set(personal_flags or [])),
        'nova': product.get('nova'), 'nutriscore': '',
    }
