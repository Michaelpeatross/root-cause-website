"""Identify a plated meal from a photo and estimate macros + health score."""
import json, re

PROMPT = (
    'Look at this meal photo. Return JSON only with: '
    '{"name":"short dish name","portion":"e.g. 1 bowl","ingredients":"comma list",'
    '"calories":int,"protein_g":int,"carbs_g":int,"fat_g":int,"sugar_g":int,"fiber_g":int,'
    '"dairy":bool,"gluten":bool,"fried":bool,"ultra_processed":bool,"notes":"one sentence"}'
)

def _vision(image_b64, mime):
    try:
        from health_advisor import _grok_vision_chat
    except Exception:
        return None
    raw = _grok_vision_chat(
        [{'type':'text','text': PROMPT}, {'type':'image_url','image_url':{'url':'data:%s;base64,%s' % (mime, image_b64), 'detail':'high'}}],
        system='Return valid JSON only. Estimate a typical restaurant portion if size is unclear.',
        temperature=0.1,
        timeout=55,
    )
    if not raw:
        return None
    raw = re.sub(r'^```json\s*|\s*```$', '', raw.strip())
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None

def _n(data, *keys):
    for key in keys:
        try:
            if data.get(key) is not None:
                return float(data.get(key))
        except (TypeError, ValueError):
            continue
    return None

def analyze_plate_for_client(image_b64, mime='image/jpeg', scan_raw=''):
    extracted = _vision(image_b64, mime or 'image/jpeg')
    if not extracted or not (extracted.get('name') or extracted.get('calories')):
        return {'ok': False, 'error': 'Could not read that plate. Get closer, better light, and fill the frame with the food.'}
    from food_scanner import client_flags_from_scan, score_product
    flags = client_flags_from_scan(scan_raw)
    ingredients = extracted.get('ingredients') or extracted.get('name') or ''
    if extracted.get('dairy'):
        ingredients += ' milk cheese cream butter'
    if extracted.get('gluten'):
        ingredients += ' wheat pasta flour bread'
    if extracted.get('fried'):
        ingredients += ' fried oil'
    product = {
        'source': 'plate-photo',
        'code': '',
        'name': (extracted.get('name') or 'Meal photo').strip(),
        'brands': extracted.get('portion') or 'Plate photo',
        'image': '',
        'ingredients': ingredients,
        'additives': ['fried'] if extracted.get('fried') else [],
        'additives_n': 1 if extracted.get('fried') or extracted.get('ultra_processed') else 0,
        'nova': 4 if extracted.get('ultra_processed') or extracted.get('fried') else 3,
        'nutriscore': '',
        'labels': [],
        'allergens': [],
        'categories': 'restaurant meal',
        'quantity': extracted.get('portion') or '',
        'nutrients': {
            'energy_kcal': _n(extracted, 'calories'),
            'sugars': _n(extracted, 'sugar_g', 'sugars'),
            'salt': None,
            'fat': _n(extracted, 'fat_g', 'fat'),
            'sat_fat': (_n(extracted, 'fat_g', 'fat') or 0) * 0.4 if extracted.get('dairy') or extracted.get('fried') else None,
            'fiber': _n(extracted, 'fiber_g', 'fiber'),
            'protein': _n(extracted, 'protein_g', 'protein'),
        },
    }
    rating = score_product(product, flags)
    macros = {
        'calories': _n(extracted, 'calories'),
        'protein': _n(extracted, 'protein_g', 'protein'),
        'carbs': _n(extracted, 'carbs_g', 'carbs'),
        'fat': _n(extracted, 'fat_g', 'fat'),
        'sugar': _n(extracted, 'sugar_g', 'sugars'),
        'fiber': _n(extracted, 'fiber_g', 'fiber'),
        'portion': extracted.get('portion') or '',
        'notes': extracted.get('notes') or '',
    }
    return {'ok': True, 'product': product, 'rating': rating, 'macros': macros, 'loggable': True}
