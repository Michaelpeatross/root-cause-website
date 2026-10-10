"""Itemized meal photos: per-food rows, sharing, edits and totals.

Pure functions shared by the web routes (and a future mobile app):
  normalize_items(raw_items, flags)  -> list of item dicts with base nutrition + score
  lookup_food(name, grams=None)      -> one item from the built-in food table (or None)
  search_foods(q)                    -> autocomplete names from the food table + guides
  compute_totals(items, meal_split)  -> totals from eaten items x size x share
  item_fraction(item, meal_split)    -> the multiplier applied to an item's base nutrition

The same math lives in static/js/meal_logic.js so totals update instantly in the
browser; tests keep the two in sync. Educational wellness estimates only.
"""
import re
import uuid

NUTRIENTS = ('calories', 'protein', 'carbs', 'fat', 'sugar', 'fiber', 'sodium_mg')
SHARE_PRESETS = {'all': 1.0, '1/2': 0.5, '1/3': 1.0 / 3, '1/4': 0.25}
MAX_ITEMS = 30

# name: (kcal, protein, carbs, fat, sugar, fiber, sodium_mg) per 100 g,
#       default portion text, default grams, processing, fried, aliases
_T = [
    ('tortilla chips', (489, 7, 63, 23, 1, 5, 350), '1 basket', 60, 'processed', True, ('chips', 'nacho chips', 'corn chips', 'chips basket')),
    ('potato chips', (536, 7, 53, 35, 0.3, 4.4, 525), '1 bag', 28, 'ultra', True, ('crisps',)),
    ('salsa', (36, 1.5, 7, 0.2, 4, 2, 600), '1/4 cup', 60, 'minimal', False, ('pico de gallo', 'salsa dip')),
    ('guacamole', (157, 2, 9, 14, 1, 6, 250), '1/4 cup', 60, 'minimal', False, ('guac', 'avocado dip')),
    ('queso dip', (220, 6, 8, 18, 3, 0, 900), '1/4 cup', 60, 'processed', False, ('queso', 'cheese dip', 'nacho cheese')),
    ('sour cream', (198, 2.4, 4.6, 19, 3.4, 0, 31), '2 tbsp', 30, 'processed', False, ()),
    ('ranch dressing', (430, 1, 6, 44, 4, 0, 900), '2 tbsp', 30, 'ultra', False, ('ranch', 'ranch dip')),
    ('vinaigrette', (290, 0, 10, 28, 8, 0, 700), '2 tbsp', 30, 'processed', False, ('salad dressing', 'dressing', 'balsamic vinaigrette', 'italian dressing')),
    ('hummus', (166, 8, 14, 10, 0.3, 6, 380), '1/4 cup', 60, 'minimal', False, ()),
    ('baked potato', (93, 2.5, 21, 0.1, 1.2, 2.2, 10), '1 medium', 175, 'whole', False, ('potato', 'jacket potato', 'plain baked potato')),
    ('loaded baked potato', (150, 5, 18, 7, 1.5, 1.8, 300), '1 large', 350, 'processed', False, ('loaded potato', 'stuffed potato')),
    ('baked sweet potato', (90, 2, 21, 0.2, 6.5, 3.3, 36), '1 medium', 150, 'whole', False, ('sweet potato',)),
    ('french fries', (312, 3.4, 41, 15, 0.3, 3.8, 210), '1 medium order', 115, 'processed', True, ('fries', 'steak fries')),
    ('sweet potato fries', (260, 2, 35, 12, 7, 4, 250), '1 order', 115, 'processed', True, ()),
    ('mashed potatoes', (113, 2, 16, 4.2, 1.5, 1.5, 320), '1 cup', 210, 'minimal', False, ('mashed potato',)),
    ('roasted potatoes', (140, 2.5, 20, 6, 1, 2, 250), '1 cup', 150, 'minimal', False, ('potato wedges', 'home fries')),
    ('onion rings', (411, 4, 38, 27, 4, 2.5, 430), '1 order', 120, 'ultra', True, ()),
    ('mozzarella sticks', (330, 15, 28, 18, 2, 1.5, 800), '4 sticks', 120, 'ultra', True, ('cheese sticks',)),
    ('side salad', (20, 1.2, 3.5, 0.2, 2, 1.5, 25), '1 bowl', 100, 'whole', False, ('garden salad', 'salad', 'green salad', 'mixed greens')),
    ('caesar salad', (158, 4, 7, 13, 2, 1.5, 350), '1 bowl', 200, 'processed', False, ()),
    ('coleslaw', (145, 1, 13, 10, 10, 1.6, 250), '1/2 cup', 90, 'processed', False, ('slaw',)),
    ('grilled vegetables', (60, 1.5, 7, 3, 4, 2.5, 150), '1 cup', 150, 'minimal', False, ('roasted vegetables', 'veggies', 'vegetables', 'mixed vegetables')),
    ('broccoli', (35, 2.4, 7, 0.4, 1.4, 3.3, 41), '1 cup', 90, 'minimal', False, ('steamed broccoli',)),
    ('green beans', (35, 1.9, 7.9, 0.3, 1.6, 3.2, 1), '1 cup', 125, 'minimal', False, ()),
    ('corn on the cob', (96, 3.4, 21, 1.5, 4.5, 2.4, 1), '1 ear', 100, 'whole', False, ('corn', 'sweet corn')),
    ('tomato', (18, 0.9, 3.9, 0.2, 2.6, 1.2, 5), '1 medium', 120, 'whole', False, ('tomatoes',)),
    ('grilled chicken breast', (165, 31, 0, 3.6, 0, 0, 74), '1 breast', 150, 'minimal', False, ('chicken breast', 'grilled chicken', 'chicken')),
    ('fried chicken', (260, 22, 10, 15, 0, 0.5, 700), '2 pieces', 200, 'processed', True, ()),
    ('chicken wings', (290, 27, 0, 19.5, 0, 0, 400), '6 wings', 180, 'processed', True, ('wings', 'buffalo wings')),
    ('chicken tenders', (270, 19, 16, 15, 0, 1, 600), '4 pieces', 150, 'processed', True, ('chicken strips', 'chicken nuggets', 'nuggets')),
    ('steak', (250, 26, 0, 15, 0, 0, 60), '1 steak', 225, 'minimal', False, ('sirloin', 'ribeye', 'beef steak')),
    ('bbq ribs', (290, 20, 8, 20, 6, 0, 550), '1/2 rack', 300, 'processed', False, ('ribs', 'pork ribs')),
    ('hamburger', (254, 13, 24, 12, 5, 1, 400), '1 burger', 220, 'processed', False, ('burger',)),
    ('cheeseburger', (263, 14, 22, 13, 5, 1, 550), '1 burger', 230, 'processed', False, ()),
    ('hot dog', (290, 10, 22, 18, 4, 1, 800), '1 hot dog', 100, 'ultra', False, ()),
    ('pizza', (266, 11, 33, 10, 3.6, 2.3, 600), '1 slice', 110, 'ultra', False, ('pizza slice', 'slice of pizza')),
    ('salmon', (206, 22, 0, 12, 0, 0, 60), '1 fillet', 150, 'minimal', False, ('grilled salmon', 'salmon fillet')),
    ('white fish', (105, 23, 0, 1, 0, 0, 80), '1 fillet', 150, 'minimal', False, ('cod', 'tilapia', 'fish', 'halibut')),
    ('shrimp', (99, 24, 0.2, 0.3, 0, 0, 111), '1 serving', 100, 'minimal', False, ('prawns', 'grilled shrimp')),
    ('tacos', (210, 9, 20, 10, 2, 3, 400), '2 tacos', 200, 'processed', False, ('taco', 'fish tacos', 'street tacos')),
    ('burrito', (190, 8, 24, 7, 1.5, 3, 450), '1 burrito', 300, 'processed', False, ()),
    ('quesadilla', (300, 13, 25, 16, 2, 1.5, 600), '1 quesadilla', 200, 'processed', False, ()),
    ('nachos', (300, 8, 30, 17, 2, 3, 550), '1 plate', 250, 'ultra', False, ('loaded nachos',)),
    ('white rice', (130, 2.7, 28, 0.3, 0, 0.4, 1), '1 cup', 160, 'minimal', False, ('rice', 'steamed rice', 'spanish rice', 'mexican rice')),
    ('brown rice', (123, 2.7, 26, 1, 0.4, 1.6, 4), '1 cup', 195, 'whole', False, ()),
    ('refried beans', (94, 5.5, 15, 1.2, 0.4, 5, 400), '1/2 cup', 120, 'processed', False, ()),
    ('black beans', (132, 8.9, 24, 0.5, 0.3, 8.7, 1), '1/2 cup', 90, 'whole', False, ('beans', 'pinto beans')),
    ('lentils', (116, 9, 20, 0.4, 1.8, 8, 2), '1 cup', 200, 'whole', False, ()),
    ('quinoa', (120, 4.4, 21, 1.9, 0.9, 2.8, 7), '1 cup', 185, 'whole', False, ()),
    ('tofu', (76, 8, 1.9, 4.8, 0.6, 0.3, 7), '1/2 cup', 125, 'minimal', False, ()),
    ('pasta with marinara', (135, 4.5, 24, 2.5, 4, 2, 280), '1 plate', 300, 'processed', False, ('spaghetti', 'pasta', 'spaghetti marinara')),
    ('mac and cheese', (164, 6.6, 19, 6.6, 2, 1, 450), '1 cup', 200, 'ultra', False, ('macaroni and cheese',)),
    ('bread roll', (280, 9, 50, 4, 5, 2, 480), '1 roll', 40, 'processed', False, ('roll', 'dinner roll', 'bread', 'bun')),
    ('garlic bread', (350, 8, 42, 16, 3, 2, 500), '1 slice', 40, 'processed', False, ()),
    ('toast', (265, 9, 49, 3.2, 5, 2.7, 490), '1 slice', 30, 'processed', False, ()),
    ('flour tortilla', (312, 8, 52, 8, 2, 3, 600), '1 tortilla', 45, 'processed', False, ('tortilla', 'tortillas')),
    ('pita', (275, 9, 56, 1.2, 1, 2, 536), '1 pita', 60, 'processed', False, ('pita bread',)),
    ('sandwich', (200, 12, 22, 7, 3, 2, 600), '1 sandwich', 200, 'processed', False, ('turkey sandwich', 'sub')),
    ('scrambled eggs', (149, 10, 1.6, 11, 1.4, 0, 145), '2 eggs', 110, 'minimal', False, ('eggs', 'egg')),
    ('fried egg', (196, 14, 0.8, 15, 0.4, 0, 207), '1 egg', 46, 'minimal', False, ()),
    ('bacon', (541, 37, 1.4, 42, 0, 0, 1717), '3 slices', 24, 'ultra', False, ()),
    ('sausage', (325, 14, 1, 29, 1, 0, 750), '2 links', 50, 'ultra', False, ('sausages', 'breakfast sausage')),
    ('pancakes', (227, 6, 28, 10, 7, 1, 440), '3 pancakes', 150, 'processed', False, ('pancake', 'waffle', 'waffles')),
    ('oatmeal', (71, 2.5, 12, 1.5, 0.3, 1.7, 49), '1 bowl', 240, 'whole', False, ('oats', 'porridge')),
    ('plain yogurt', (61, 3.5, 4.7, 3.3, 4.7, 0, 46), '1 cup', 245, 'minimal', False, ('yogurt', 'greek yogurt')),
    ('banana', (89, 1.1, 23, 0.3, 12, 2.6, 1), '1 medium', 118, 'whole', False, ('bananas',)),
    ('apple', (52, 0.3, 14, 0.2, 10, 2.4, 1), '1 medium', 180, 'whole', False, ('apples',)),
    ('berries', (57, 0.7, 14, 0.3, 10, 2.4, 1), '1 cup', 148, 'whole', False, ('blueberries', 'strawberries', 'raspberries', 'mixed berries')),
    ('orange', (47, 0.9, 12, 0.1, 9, 2.4, 0), '1 medium', 130, 'whole', False, ('oranges',)),
    ('avocado', (160, 2, 8.5, 15, 0.7, 6.7, 7), '1/2 avocado', 100, 'whole', False, ()),
    ('cheese', (402, 25, 1.3, 33, 0.5, 0, 621), '1 slice', 28, 'processed', False, ('shredded cheese', 'cheddar')),
    ('butter', (717, 0.9, 0.1, 81, 0.1, 0, 11), '1 pat', 5, 'processed', False, ()),
    ('gravy', (50, 1.5, 5, 2.5, 0.5, 0.2, 550), '1/4 cup', 60, 'processed', False, ()),
    ('ketchup', (101, 1, 27, 0.1, 22, 0.3, 907), '1 tbsp', 17, 'ultra', False, ()),
    ('bbq sauce', (172, 0.8, 41, 0.6, 33, 0.9, 1027), '2 tbsp', 35, 'ultra', False, ('barbecue sauce',)),
    ('mixed nuts', (607, 20, 21, 54, 4, 7, 3), '1 handful', 30, 'whole', False, ('nuts', 'almonds', 'peanuts')),
    ('chicken noodle soup', (30, 2, 3.5, 1, 0.5, 0.4, 340), '1 bowl', 360, 'processed', False, ('soup',)),
    ('chili', (110, 8, 10, 4.5, 3, 3, 420), '1 bowl', 250, 'processed', False, ()),
    ('sushi roll', (129, 2.9, 18, 3.7, 3, 1, 430), '1 roll (8 pcs)', 200, 'processed', False, ('sushi', 'california roll')),
    ('ice cream', (207, 3.5, 24, 11, 21, 0.7, 80), '1/2 cup', 66, 'ultra', False, ()),
    ('cookie', (488, 5, 64, 24, 35, 2, 350), '1 cookie', 40, 'ultra', False, ('cookies',)),
    ('cake', (370, 4, 53, 16, 36, 1, 300), '1 slice', 80, 'ultra', False, ('brownie', 'dessert')),
    ('soda', (41, 0, 10.6, 0, 10.6, 0, 4), '1 can', 355, 'ultra', False, ('cola', 'soft drink', 'coke', 'pop')),
    ('orange juice', (45, 0.7, 10, 0.2, 8.4, 0.2, 1), '1 glass', 250, 'processed', False, ('juice',)),
    ('beer', (43, 0.5, 3.6, 0, 0, 0, 4), '1 pint', 473, 'processed', False, ()),
    ('wine', (83, 0.1, 2.6, 0, 0.6, 0, 5), '1 glass', 150, 'processed', False, ('red wine', 'white wine')),
    ('margarita', (130, 0, 15, 0, 13, 0, 300), '1 glass', 240, 'ultra', False, ()),
    ('coffee', (1, 0.1, 0, 0, 0, 0, 2), '1 cup', 240, 'whole', False, ('black coffee',)),
    ('water', (0, 0, 0, 0, 0, 0, 0), '1 glass', 250, 'whole', False, ('sparkling water', 'iced water')),
    ('iced tea', (1, 0, 0.3, 0, 0, 0, 3), '1 glass', 350, 'whole', False, ('tea', 'unsweetened tea')),
]

FOOD_TABLE = {}
_ALIAS = {}
for _name, _vals, _portion, _grams, _proc, _fried, _aliases in _T:
    FOOD_TABLE[_name] = {'per100': dict(zip(NUTRIENTS, _vals)), 'portion': _portion, 'grams': _grams,
                         'processing': _proc, 'fried': _fried}
    _ALIAS[_name] = _name
    for _a in _aliases:
        _ALIAS.setdefault(_a, _name)


def _norm(text):
    text = re.sub(r'[^a-z0-9 ]+', ' ', str(text or '').lower())
    return re.sub(r'\s+', ' ', text).strip()


def _num(val, default=None):
    try:
        if val is None or val == '':
            return default
        n = float(val)
        if n != n:  # NaN
            return default
        return n
    except (TypeError, ValueError):
        return default


def match_food(name):
    """Best table key for a free-text name ("Basket of tortilla chips" -> "tortilla chips")."""
    n = _norm(name)
    if not n:
        return None
    if n in _ALIAS:
        return _ALIAS[n]
    if n.endswith('s') and n[:-1] in _ALIAS:
        return _ALIAS[n[:-1]]
    best, best_len = None, 0
    padded = ' %s ' % n
    for alias, key in _ALIAS.items():
        if (' %s ' % alias) in padded or (' %ss ' % alias) in padded:
            if len(alias) > best_len:
                best, best_len = key, len(alias)
    return best


def lookup_food(name, grams=None):
    """Item dict (base nutrition for `grams`, default portion if None) or None."""
    key = match_food(name)
    if not key:
        return None
    row = FOOD_TABLE[key]
    g = _num(grams)
    if not g or g <= 0:
        g = row['grams']
    base = {k: round(v * g / 100.0, 1) for k, v in row['per100'].items()}
    portion = '%s (%d g)' % (row['portion'], round(g)) if g == row['grams'] else '%d g' % round(g)
    return {
        'name': str(name).strip()[:60] or key, 'matched': key, 'portion': portion,
        'grams': round(g), 'base': base, 'processing': row['processing'], 'fried': row['fried'], 'source': 'database',
    }


def search_foods(q, limit=12):
    """Autocomplete names: built-in table (with nutrition) first, then whole-food guide names."""
    n = _norm(q)
    if len(n) < 1:
        return []
    out, seen = [], set()

    def add(name, kcal=None, portion=''):
        k = name.lower()
        if k in seen:
            return
        seen.add(k)
        out.append({'name': name[:1].upper() + name[1:], 'calories': kcal, 'portion': portion, 'has_nutrition': kcal is not None})

    starts, contains = [], []
    for alias, key in _ALIAS.items():
        if alias.startswith(n) or (' ' + n) in (' ' + alias):
            (starts if alias.startswith(n) else contains).append((alias, key))
    for alias, key in sorted(starts, key=lambda x: len(x[0])) + sorted(contains, key=lambda x: len(x[0])):
        row = FOOD_TABLE[key]
        add(key, int(round(row['per100']['calories'] * row['grams'] / 100.0)), row['portion'])
        if len(out) >= limit:
            return out
    try:
        from food_guides import CANDIDATES
        for name, _tags in CANDIDATES:
            clean = re.sub(r'\s+(if tolerated|if gut calm|occasional|live)$', '', name)
            if n in clean.lower():
                add(clean)
                if len(out) >= limit:
                    break
    except Exception:
        pass
    return out[:limit]


# ------------------------------------------------------------------ scoring
def _score_item(item, flags=None):
    try:
        from food_scanner import score_product
        product = {
            'name': item.get('name') or 'item', 'ingredients': item.get('name') or '',
            'categories': item.get('name') or '',
            'components': [{'name': item.get('name') or 'item', 'processing': item.get('processing') or 'processed',
                            'share': 1.0, 'fried': bool(item.get('fried'))}],
        }
        r = score_product(product, flags or [])
        return {'score': r.get('score'), 'label': r.get('label') or '', 'color': r.get('color') or '#555',
                'band': r.get('band') or '', 'personal_notes': r.get('personal_notes') or []}
    except Exception:
        return {'score': None, 'label': '', 'color': '#555', 'band': '', 'personal_notes': []}


def _clean_processing(val):
    val = str(val or '').lower().strip()
    return val if val in ('whole', 'minimal', 'processed', 'ultra') else 'processed'


def make_item(raw, flags=None):
    """Normalize one item from the vision model, the client, or the food table."""
    raw = dict(raw or {})
    name = str(raw.get('name') or 'Food').strip()[:60] or 'Food'
    name = name[:1].upper() + name[1:]  # "tortilla chips" -> "Tortilla chips"
    base_in = raw.get('base') if isinstance(raw.get('base'), dict) else raw
    base = {
        'calories': _num(base_in.get('calories')),
        'protein': _num(base_in.get('protein', base_in.get('protein_g'))),
        'carbs': _num(base_in.get('carbs', base_in.get('carbs_g'))),
        'fat': _num(base_in.get('fat', base_in.get('fat_g'))),
        'sugar': _num(base_in.get('sugar', base_in.get('sugar_g'))),
        'fiber': _num(base_in.get('fiber', base_in.get('fiber_g'))),
        'sodium_mg': _num(base_in.get('sodium_mg')),
    }
    grams = _num(raw.get('grams'))
    table = lookup_food(name, grams)
    source = raw.get('source') or 'photo'
    # Missing or impossible calories (> 9.5 kcal per gram) -> use the food table.
    implausible = grams and base['calories'] is not None and base['calories'] > grams * 9.5
    if table and (base['calories'] is None or implausible):
        base = dict(table['base'])
        source = 'database'
    elif table:
        for k, v in table['base'].items():
            if base.get(k) is None:
                base[k] = v
    for k in NUTRIENTS:
        if base.get(k) is not None:
            base[k] = max(0.0, round(base[k], 1))
    processing = _clean_processing(raw.get('processing') or (table or {}).get('processing'))
    fried = bool(raw.get('fried')) if raw.get('fried') is not None else bool((table or {}).get('fried'))
    share = _num(raw.get('share'), 1.0)
    share = min(1.0, max(0.05, share)) if share else 1.0
    size = _num(raw.get('size'), 1.0) or 1.0
    size = min(10.0, max(0.1, size))
    item = {
        'id': str(raw.get('id') or uuid.uuid4().hex[:10])[:40],
        'name': name,
        'portion': str(raw.get('portion') or (table or {}).get('portion') or '').strip()[:60],
        'grams': int(round(grams)) if grams else ((table or {}).get('grams')),
        'base': base,
        'size': size,
        'eaten': raw.get('eaten') is not False,
        'share': share,
        'share_override': bool(raw.get('share_override')),
        'processing': processing,
        'fried': fried,
        'partly_eaten': bool(raw.get('partly_eaten')),
        'shared_dish': bool(raw.get('shared_dish', raw.get('shared'))),
        'confidence': str(raw.get('confidence') or '').lower()[:10],
        'source': str(source)[:20],
    }
    item.update(_score_item(item, flags))
    return item


def normalize_items(raw_items, flags=None):
    out = []
    for raw in (raw_items or [])[:MAX_ITEMS]:
        if isinstance(raw, dict) and (raw.get('name') or raw.get('calories') is not None):
            out.append(make_item(raw, flags))
    return out


# ------------------------------------------------------------------ math
def item_fraction(item, meal_split=1):
    """Multiplier on base nutrition: 0 if not eaten, else size x my share."""
    if not item or item.get('eaten') is False:
        return 0.0
    size = _num(item.get('size'), 1.0) or 1.0
    if item.get('share_override'):
        share = _num(item.get('share'), 1.0)
    else:
        split = int(_num(meal_split, 1) or 1)
        share = 1.0 / split if split > 1 else _num(item.get('share'), 1.0)
    share = min(1.0, max(0.0, share if share is not None else 1.0))
    return size * share


def compute_totals(items, meal_split=1):
    totals = {k: 0.0 for k in NUTRIENTS}
    weighted, weight, eaten = 0.0, 0.0, 0
    for item in items or []:
        f = item_fraction(item, meal_split)
        if f <= 0:
            continue
        eaten += 1
        base = item.get('base') or {}
        for k in NUTRIENTS:
            totals[k] += (_num(base.get(k), 0.0) or 0.0) * f
        score = _num(item.get('score'))
        if score is not None:
            w = (_num(base.get('calories'), 0.0) or 0.0) * f or 1.0
            weighted += score * w
            weight += w
    out = {k: (int(round(v)) if k in ('calories', 'sodium_mg') else round(v, 1)) for k, v in totals.items()}
    out['items_eaten'] = eaten
    out['score'] = int(round(weighted / weight)) if weight else None
    return out


def meal_name(items, fallback='Meal'):
    names = [i.get('name') for i in items or [] if i.get('eaten') is not False and i.get('name')]
    if not names:
        return fallback
    if len(names) <= 3:
        return ', '.join(names)[:80]
    return ('%s +%d more' % (', '.join(names[:2]), len(names) - 2))[:80]


def compact_items(items, meal_split=1):
    """What gets stored in the diary entry so the meal can be reopened and edited."""
    keep = ('id', 'name', 'portion', 'grams', 'base', 'size', 'eaten', 'share', 'share_override',
            'processing', 'fried', 'partly_eaten', 'shared_dish', 'score', 'label', 'color', 'source')
    return [{k: i.get(k) for k in keep} for i in (items or [])[:MAX_ITEMS]]
