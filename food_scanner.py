"""Food scanner: barcode, label photo, whole-food-first score 1-100."""
import json, re, urllib.parse, urllib.request
try:
    from report_generator import _parse_lines
except Exception:
    def _parse_lines(raw):
        return []

OFF_UA = 'RootCauseBioenergetics/1.0 (https://www.root-cause-test.com)'
# Legacy table (pre whole-food-v2); scoring now lives in food_score_v2.py.
ADDITIVE_PENALTY = {'e621':12,'e627':10,'e631':10,'e102':10,'e110':10,'e129':10,'e211':8,'e320':12,'e321':12,'e951':10,'e950':8,'e955':8,'e250':12,'e251':12,'e150d':6}
# Personal filters come from the user's own wellness scan. Wording stays
# preference-based (no diagnosis or treatment claims).
PERSONAL_TRIGGERS = {
    'candida': {'keywords':('candida','yeast','fung','sugar','thrush'),'penalize':('sugar','glucose','fructose','sucrose','corn syrup','dextrose','maltodextrin','yeast','soda','juice'),'reason':'Your sugar & yeast filter (from your wellness scan) flags this item.'},
    'dairy': {'keywords':('dairy','milk','lactose','casein','whey'),'penalize':('milk','cream','cheese','butter','whey','casein','lactose','yogurt'),'reason':'Your dairy filter flags this item.'},
    'gluten': {'keywords':('gluten','wheat','celiac','gliadin'),'penalize':('wheat','barley','rye','malt','gluten','flour'),'reason':'Your gluten filter flags this item.'},
    'gut': {'keywords':('gut','intestin','digest','ibs','bloating','colon'),'penalize':('emulsifier','carrageenan','polysorbate','artificial','hydrogenated'),'reason':'Your gut-comfort filter flags these additives.'},
    'liver': {'keywords':('liver','detox','alcohol','hepat'),'penalize':('alcohol','beer','wine','high fructose'),'reason':'Your alcohol & additive filter flags this item.'},
}

def _http_get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={'User-Agent': OFF_UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))

def _code_variants(code):
    code = re.sub(r'\D+', '', code or '')
    out = []
    for c in (code, code.lstrip('0') or code):
        if c and c not in out:
            out.append(c)
    if code.isdigit() and len(code) == 12:
        padded = '0' + code
        if padded not in out:
            out.append(padded)
    if code.isdigit() and len(code) == 11:
        for extra in ('0' + code, '00' + code):
            if extra not in out:
                out.append(extra)
    return [c for c in out if 8 <= len(c) <= 14]

def lookup_barcode(code):
    variants = _code_variants(code)
    hosts = (
        'https://world.openfoodfacts.org/api/v2/product/{}.json',
        'https://world.openfoodfacts.org/api/v0/product/{}.json',
        'https://us.openfoodfacts.org/api/v2/product/{}.json',
        'https://us.openfoodfacts.org/api/v0/product/{}.json',
    )
    for variant in variants:
        for tmpl in hosts:
            try:
                data = _http_get_json(tmpl.format(variant))
            except Exception:
                continue
            product = (data or {}).get('product')
            if data and data.get('status') == 1 and product:
                return normalize_off_product(product, variant)
    return None

def search_product_name(query):
    query = (query or '').strip()
    if len(query) < 3:
        return []
    params = urllib.parse.urlencode({'search_terms': query, 'search_simple': 1, 'action': 'process', 'json': 1, 'page_size': 8})
    try:
        data = _http_get_json('https://world.openfoodfacts.org/cgi/search.pl?' + params)
    except Exception:
        return []
    out = []
    for product in data.get('products') or []:
        name = (product.get('product_name') or '').strip()
        code = str(product.get('code') or '').strip()
        if name and code:
            out.append({'code': code, 'name': name, 'brands': product.get('brands') or '', 'image': product.get('image_front_small_url') or '', 'nutriscore': (product.get('nutriscore_grade') or '').upper()})
    return out

def normalize_off_product(product, code=''):
    nutriments = product.get('nutriments') or {}
    def num(*keys):
        for key in keys:
            val = nutriments.get(key)
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
        return None
    additives = [str(a).lower() for a in (product.get('additives_tags') or [])]
    return {
        'source': 'openfoodfacts', 'code': str(code or product.get('code') or ''),
        'name': (product.get('product_name') or product.get('generic_name') or 'Unknown product').strip(),
        'brands': product.get('brands') or '',
        'image': product.get('image_url') or product.get('image_front_small_url') or '',
        'ingredients': product.get('ingredients_text_en') or product.get('ingredients_text') or '',
        'additives': additives, 'additives_n': product.get('additives_n') or len(additives),
        'nova': product.get('nova_group'), 'nutriscore': (product.get('nutriscore_grade') or product.get('nutrition_grades') or '').upper(),
        'labels': product.get('labels_tags') or [], 'allergens': product.get('allergens_tags') or [],
        'categories': product.get('categories') or '', 'quantity': product.get('quantity') or '',
        'nutrients': {
            'energy_kcal': num('energy-kcal_100g','energy-kcal'),
            'sugars': num('sugars_100g','sugars'),
            'salt': num('salt_100g','salt'),
            'sodium': num('sodium_100g','sodium'),
            'fat': num('fat_100g','fat'),
            'sat_fat': num('saturated-fat_100g','saturated-fat'),
            'fiber': num('fiber_100g','fiber'),
            'protein': num('proteins_100g','proteins'),
            'carbs': num('carbohydrates_100g','carbohydrates'),
            'carbohydrates': num('carbohydrates_100g','carbohydrates'),
        },
    }

def client_flags_from_scan(raw_data):
    flags = set()
    text = (raw_data or '').lower() + ' ' + ' '.join(f.get('label','') for f in _parse_lines(raw_data or '')).lower()
    for flag, spec in PERSONAL_TRIGGERS.items():
        if any(k in text for k in spec['keywords']):
            flags.add(flag)
    return sorted(flags)

def score_product(product, personal_flags=None):
    """Whole-food-first 1-100 score (see food_score_v2.py / SPEC.md)."""
    from food_score_v2 import score_product_v2
    return score_product_v2(product, personal_flags, PERSONAL_TRIGGERS)

def extract_label_from_image(image_b64, mime='image/jpeg'):
    try:
        from health_advisor import _grok_vision_chat
    except Exception:
        return None
    prompt = ('Read this food photo. It may be a packaged label OR an unpackaged food (fruit, vegetable, egg, meat, fish, nuts, grains). '
              'Copy the ingredient list exactly as printed (empty string if there is no label). Nutrition values per 100 g when shown. '
              'Return JSON only: {"barcode":"digits or null","name":"","brand":"","ingredients":"","energy_kcal":null,"carbs_100g":null,'
              '"sugars_100g":null,"salt_100g":null,"sat_fat_100g":null,"fiber_100g":null,"protein_100g":null,"sodium_mg":null,'
              '"additives":[],"organic":false,"has_label":true,"whole_food":false,'
              '"food_type":"packaged|produce|egg|meat_fish|legume|nut_seed|whole_grain|dairy|other","nova_estimate":null}. '
              'Set whole_food true only for a single unprocessed food with nothing added. nova_estimate is 1-4 or null.')
    raw = _grok_vision_chat([{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':'data:%s;base64,%s' % (mime, image_b64),'detail':'high'}}], system='Return valid JSON only.', temperature=0.1, timeout=50)
    if not raw:
        return None
    raw = re.sub(r'^```json\s*', '', raw.strip())
    raw = re.sub(r'^```\s*|\s*```$', '', raw)
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None

def product_from_label_extract(extracted):
    if not extracted:
        return None
    nutrients = {}
    for src, dest in (('sugars_100g','sugars'),('salt_100g','salt'),('sat_fat_100g','sat_fat'),('fiber_100g','fiber'),('protein_100g','protein'),('carbs_100g','carbs'),('energy_kcal','energy_kcal')):
        try:
            nutrients[dest] = float(extracted[src]) if extracted.get(src) is not None else None
        except (TypeError, ValueError):
            nutrients[dest] = None
    try:
        if extracted.get('sodium_mg') is not None:
            nutrients['sodium'] = float(extracted.get('sodium_mg')) / 1000.0
    except (TypeError, ValueError):
        pass
    additives = []
    for item in extracted.get('additives') or []:
        text = str(item).lower()
        m = re.search(r'e\s*(\d{3,4}[a-z]?)', text)
        additives.append('e' + m.group(1) if m else text)
    ingredients = (extracted.get('ingredients') or '').strip()
    name = (extracted.get('name') or '').strip()
    if not (name or ingredients or any(v is not None for v in nutrients.values())):
        return None
    # NOVA is derived from the ingredient list by the scorer. The model's
    # estimate is only used when there is no ingredient list at all.
    nova = None
    if not ingredients:
        try:
            est = int(extracted.get('nova_estimate')) if extracted.get('nova_estimate') is not None else None
            nova = est if est in (1, 2, 3, 4) else None
        except (TypeError, ValueError):
            nova = None
    whole_hint = bool(extracted.get('whole_food')) and not ingredients and not additives
    return {'source':'label-photo','code': re.sub(r'\D+','', str(extracted.get('barcode') or '')),'name': name or 'Food photo','brands': extracted.get('brand') or '','image':'','ingredients': ingredients,'additives': additives,'additives_n': len(additives),'nova': nova,'whole_food_hint': whole_hint,'nutriscore':'','labels': ['en:organic'] if extracted.get('organic') else [],'allergens':[],'categories': extracted.get('food_type') or '','quantity':'','nutrients': nutrients}

def scan_barcode_for_client(code, scan_raw=''):
    digits = re.sub(r'\D+', '', code or '')
    product = lookup_barcode(digits)
    if not product:
        return {'ok': False, 'error': 'No product in the grocery database for barcode %s. Use Label photo or Search name (store brands are often missing).' % (digits or 'blank')}
    flags = client_flags_from_scan(scan_raw)
    return {'ok': True, 'product': product, 'rating': score_product(product, flags)}

def scan_photo_for_client(image_b64, mime='image/jpeg', scan_raw=''):
    extracted = extract_label_from_image(image_b64, mime)
    if not extracted:
        return {'ok': False, 'error': 'Could not read that label. Try a sharper photo of ingredients + Nutrition Facts, or type the barcode.'}
    barcode = re.sub(r'\D+', '', str(extracted.get('barcode') or ''))
    product = lookup_barcode(barcode) if len(barcode) >= 8 else None
    if product is None:
        product = product_from_label_extract(extracted)
    if not product:
        return {'ok': False, 'error': 'Label was readable but not enough data to score.'}
    flags = client_flags_from_scan(scan_raw)
    return {'ok': True, 'product': product, 'rating': score_product(product, flags)}
