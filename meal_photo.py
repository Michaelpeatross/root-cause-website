"""Identify a plated meal from a photo and estimate macros + whole-food score."""
import json, re

PROMPT = (
    'Look at this meal photo. List each visible food component and how processed it is. '
    'processing must be one of: "whole" (unprocessed: fresh produce, eggs, plain meat/fish, beans, nuts, whole grains), '
    '"minimal" (whole food cooked simply with salt, herbs, olive oil or butter), '
    '"processed" (cheese, bread, cured or canned foods, simple sauces), '
    '"ultra" (packaged snacks, soda, processed meats, fast food, sugary sauces, desserts, breaded or deep-fried items). '
    'share is the approximate fraction of the plate (all shares add to about 1). '
    'Return JSON only: {"name":"short dish name","portion":"e.g. 1 bowl",'
    '"components":[{"name":"","processing":"whole|minimal|processed|ultra","share":0.0,"fried":false}],'
    '"ingredients":"comma list","calories":int,"protein_g":int,"carbs_g":int,"fat_g":int,"sugar_g":int,"fiber_g":int,'
    '"dairy":bool,"gluten":bool,"fried":bool,"ultra_processed":bool,"notes":"one neutral sentence, no health claims"}'
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

def _components(extracted):
    comps = []
    for c in extracted.get('components') or []:
        if isinstance(c, dict) and (c.get('name') or c.get('processing')):
            comps.append({
                'name': str(c.get('name') or 'item')[:60],
                'processing': str(c.get('processing') or 'processed').lower(),
                'share': c.get('share'),
                'fried': bool(c.get('fried')),
            })
    if comps:
        return comps
    # Older/partial model output: fall back to the dish-level booleans.
    level = 'ultra' if extracted.get('ultra_processed') else 'processed'
    return [{'name': extracted.get('name') or 'meal', 'processing': level, 'share': 1.0, 'fried': bool(extracted.get('fried'))}]

def build_plate_product(extracted):
    ingredients = extracted.get('ingredients') or extracted.get('name') or ''
    fat = _n(extracted, 'fat_g', 'fat')
    return {
        'source': 'plate-photo',
        'code': '',
        'name': (extracted.get('name') or 'Meal photo').strip(),
        'brands': extracted.get('portion') or 'Plate photo',
        'image': '',
        'ingredients': ingredients,
        'components': _components(extracted),
        'additives': [],
        'additives_n': 0,
        'nova': 4 if extracted.get('ultra_processed') else None,
        'nutriscore': '',
        'labels': [],
        'allergens': [],
        'categories': 'meal photo' + (' dairy' if extracted.get('dairy') else '') + (' wheat gluten' if extracted.get('gluten') else ''),
        'quantity': extracted.get('portion') or '',
        'nutrients': {
            'energy_kcal': _n(extracted, 'calories'),
            'sugars': _n(extracted, 'sugar_g', 'sugars'),
            'salt': None,
            'fat': fat,
            'sat_fat': None,
            'fiber': _n(extracted, 'fiber_g', 'fiber'),
            'protein': _n(extracted, 'protein_g', 'protein'),
            'carbs': _n(extracted, 'carbs_g', 'carbs'),
        },
    }

def analyze_plate_for_client(image_b64, mime='image/jpeg', scan_raw=''):
    extracted = _vision(image_b64, mime or 'image/jpeg')
    if not extracted or not (extracted.get('name') or extracted.get('calories')):
        return {'ok': False, 'error': 'Could not read that plate. Get closer, better light, and fill the frame with the food.'}
    from food_scanner import client_flags_from_scan, score_product
    flags = client_flags_from_scan(scan_raw)
    product = build_plate_product(extracted)
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
