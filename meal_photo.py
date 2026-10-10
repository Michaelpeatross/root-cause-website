"""Identify every food in a meal photo (one plate or a shared table) and estimate
per-item nutrition + whole-food score. Results are an editable item list; nothing
is logged until the user taps Save meal."""
import json, re

PROCESSING_HELP = (
    'Name each protein from its shape. Several thick, craggy, pale breaded strips are chicken tenders, not fish. '
    'Fish is one or two flat wide fillets. Wings show a bone. Fries in a cup are fries, not the protein. '
    'Do not call breaded strips fish and chips. '
    'processing must be one of: "whole" (unprocessed: fresh produce, eggs, plain meat or fish, beans, nuts, whole grains), '
    '"minimal" (whole food cooked simply with salt, herbs, olive oil or butter), '
    '"processed" (breaded or deep-fried restaurant food such as chicken tenders and fries, cheese, bread, table sauces like honey mustard or barbecue), '
    '"ultra" (only a packaged snack, soda, candy, or a product whose label lists industrial additives). '
    'A restaurant plate is not ultra and does not contain industrial additives. '
)

PROMPT = (
    'Look at this food photo. It may be one plate OR a whole table with several plates, shared appetizers, '
    'sides, dips, sauces and drinks, some partly eaten. List EVERY distinct food or drink as its own item. '
    'Never merge separate foods into one dish name: a basket of chips, each dip or sauce bowl (salsa, queso, '
    'guacamole, ranch, sour cream), each side, each salad, each main and each drink is a separate item. '
    'A single built dish (a burger, a burrito, a loaded potato) can be one item, but anything served beside it '
    'is separate. If the same food appears on several plates, list it once per plate. '
    'For each item estimate the amount that was SERVED: if it looks partly eaten, estimate the original serving '
    'and set partly_eaten true. Set shared true for communal dishes in the middle of the table or clearly meant '
    'for several people (chip baskets, dips, appetizers). people is how many diners the plates, glasses and '
    'place settings suggest (1 if unclear). '
    + PROCESSING_HELP +
    'Nutrition numbers are for the whole served amount of that item. sodium is in mg. '
    'Return JSON only: {"name":"short meal name","people":1,"items":[{"name":"plain food name",'
    '"portion":"e.g. 1 basket","grams":0,"calories":0,"protein_g":0,"carbs_g":0,"fat_g":0,"sugar_g":0,'
    '"fiber_g":0,"sodium_mg":0,"processing":"whole|minimal|processed|ultra","fried":false,'
    '"partly_eaten":false,"shared":false,"confidence":"high|medium|low"}],'
    '"notes":"one neutral sentence, no health claims"}'
)

TEXT_PROMPT = (
    'Estimate typical nutrition for this food as served in the US: "%s"%s. '
    + PROCESSING_HELP +
    'Return JSON only: {"name":"","portion":"e.g. 1 cup","grams":0,"calories":0,"protein_g":0,"carbs_g":0,'
    '"fat_g":0,"sugar_g":0,"fiber_g":0,"sodium_mg":0,"processing":"whole|minimal|processed|ultra","fried":false}'
)


def _parse_json(raw):
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r'\{.*\}', raw, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def _vision(image_b64, mime):
    try:
        from health_advisor import _grok_vision_chat
    except Exception:
        return None
    raw = _grok_vision_chat(
        [{'type': 'text', 'text': PROMPT}, {'type': 'image_url', 'image_url': {'url': 'data:%s;base64,%s' % (mime, image_b64), 'detail': 'high'}}],
        system='Return valid JSON only. Estimate a typical restaurant portion if size is unclear.',
        temperature=0.1,
        timeout=55,
    )
    return _parse_json(raw)


def estimate_food_text(name, portion=''):
    """Free-text nutrition re-lookup for a renamed item that is not in the food table."""
    try:
        from health_advisor import _grok_chat
    except Exception:
        return None
    raw = _grok_chat(
        TEXT_PROMPT % (str(name)[:80].replace('"', "'"), (', portion: %s' % str(portion)[:40]) if portion else ''),
        system='Return valid JSON only.',
        temperature=0.1,
        timeout=20,
    )
    data = _parse_json(raw)
    if not data or _n(data, 'calories') is None:
        return None
    data['name'] = str(name).strip()[:60]
    return data


def _n(data, *keys):
    for key in keys:
        try:
            if data.get(key) is not None:
                return float(data.get(key))
        except (TypeError, ValueError):
            continue
    return None


def _raw_items(extracted):
    """Items from the new format, or from the older {components, calories} format."""
    items = [i for i in (extracted.get('items') or []) if isinstance(i, dict) and i.get('name')]
    if items:
        return items
    comps = [c for c in (extracted.get('components') or []) if isinstance(c, dict) and c.get('name')]
    total = {k: _n(extracted, k + '_g', k) for k in ('protein', 'carbs', 'fat', 'sugar', 'fiber')}
    kcal = _n(extracted, 'calories')
    if not comps:
        return [{'name': extracted.get('name') or 'Meal', 'portion': extracted.get('portion') or '',
                 'calories': kcal, 'protein_g': total['protein'], 'carbs_g': total['carbs'], 'fat_g': total['fat'],
                 'sugar_g': total['sugar'], 'fiber_g': total['fiber'],
                 'processing': 'ultra' if extracted.get('ultra_processed') else 'processed',
                 'fried': bool(extracted.get('fried'))}]
    out = []
    for c in comps:
        share = _n(c, 'share') or (1.0 / len(comps))
        row = {'name': c.get('name'), 'processing': c.get('processing'), 'fried': c.get('fried'), 'portion': ''}
        if kcal is not None:
            row['calories'] = round(kcal * share)
        for k, v in total.items():
            if v is not None:
                row[k + '_g'] = round(v * share, 1)
        out.append(row)
    return out


def build_plate_product(extracted, items=None):
    """Legacy single-product view of the meal (kept for older clients and history)."""
    from meal_items import compute_totals, normalize_items
    if items is None:
        items = normalize_items(_raw_items(extracted))
    totals = compute_totals(items, 1) if items else {}
    kcal_sum = sum((i['base'].get('calories') or 0) for i in items) or 0
    comps = []
    for i in items:
        share = ((i['base'].get('calories') or 0) / kcal_sum) if kcal_sum else 1.0 / max(1, len(items))
        comps.append({'name': i['name'], 'processing': i['processing'], 'share': round(share, 3), 'fried': i['fried']})
    names = ', '.join(i['name'] for i in items)
    return {
        'source': 'plate-photo', 'code': '',
        'name': (extracted.get('name') or 'Meal photo').strip()[:80],
        'brands': 'Plate photo', 'image': '',
        'ingredients': names,
        'components': comps or [{'name': extracted.get('name') or 'meal', 'processing': 'processed', 'share': 1.0, 'fried': False}],
        'additives': [], 'additives_n': 0, 'nova': None, 'nutriscore': '', 'labels': [], 'allergens': [],
        'categories': 'meal photo ' + names.lower(), 'quantity': '',
        'nutrients': {
            'energy_kcal': totals.get('calories'), 'sugars': totals.get('sugar'), 'salt': None,
            'fat': totals.get('fat'), 'sat_fat': None, 'fiber': totals.get('fiber'),
            'protein': totals.get('protein'), 'carbs': totals.get('carbs'),
        },
    }


def analyze_plate_for_client(image_b64, mime='image/jpeg', scan_raw=''):
    extracted = _vision(image_b64, mime or 'image/jpeg')
    if not extracted or not (extracted.get('items') or extracted.get('name') or extracted.get('calories')):
        return {'ok': False, 'error': 'Could not read that photo. Get closer, use better light, and fill the frame with the food.'}
    from food_scanner import client_flags_from_scan, score_product
    from meal_items import normalize_items, compute_totals
    flags = client_flags_from_scan(scan_raw)
    items = normalize_items(_raw_items(extracted), flags)
    if not items:
        return {'ok': False, 'error': 'No food found in that photo. Try again with the food filling the frame.'}
    try:
        people = int(_n(extracted, 'people') or 1)
    except (TypeError, ValueError):
        people = 1
    people = max(1, min(12, people))
    # Shared table: communal dishes start split between the diners (easy to change).
    if people > 1:
        for i in items:
            if i.get('shared_dish'):
                i['share'] = round(1.0 / people, 4)
                i['share_override'] = True
    product = build_plate_product(extracted, items)
    rating = score_product(product, flags)
    totals = compute_totals(items, 1)
    macros = {
        'calories': totals['calories'], 'protein': totals['protein'], 'carbs': totals['carbs'],
        'fat': totals['fat'], 'sugar': totals['sugar'], 'fiber': totals['fiber'],
        'portion': '%d items' % len(items), 'notes': str(extracted.get('notes') or '')[:240],
    }
    return {
        'ok': True, 'kind': 'meal', 'items': items, 'people': people,
        'shared_table': people > 1 or any(i.get('shared_dish') for i in items),
        'meal_name': product['name'], 'totals': totals,
        'product': product, 'rating': rating, 'macros': macros, 'loggable': True, 'saved': False,
    }
