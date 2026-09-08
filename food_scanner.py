"""Yuka-style food scanner: barcode, label photo, score 1-100."""
import json, re, urllib.error, urllib.parse, urllib.request
try:
    from report_generator import _parse_lines
except Exception:
    def _parse_lines(raw):
        return []

OFF_UA = 'RootCauseBioenergetics/1.0'
OFF_PRODUCT = 'https://world.openfoodfacts.org/api/v2/product/{code}.json'
OFF_SEARCH = 'https://world.openfoodfacts.org/cgi/search.pl'
ADDITIVE_PENALTY = {'e621':12,'e627':10,'e631':10,'e102':10,'e110':10,'e129':10,'e211':8,'e320':12,'e321':12,'e951':10,'e950':8,'e955':8,'e250':12,'e251':12,'e150d':6}
PERSONAL_TRIGGERS = {
    'candida': {'keywords':('candida','yeast','fung','sugar','thrush'),'penalize':('sugar','glucose','fructose','sucrose','corn syrup','dextrose','maltodextrin','yeast','soda','juice'),'reason':'Sugar and yeast-heavy foods clash with a candida pattern.'},
    'dairy': {'keywords':('dairy','milk','lactose','casein','whey'),'penalize':('milk','cream','cheese','butter','whey','casein','lactose','yogurt'),'reason':'Dairy ingredients match a dairy sensitivity pattern.'},
    'gluten': {'keywords':('gluten','wheat','celiac','gliadin'),'penalize':('wheat','barley','rye','malt','gluten','flour'),'reason':'Gluten grains showed as a sensitivity pattern.'},
    'gut': {'keywords':('gut','intestin','digest','ibs','bloating','colon'),'penalize':('emulsifier','carrageenan','polysorbate','artificial','hydrogenated'),'reason':'Ultra-processed additives are harder on a stressed gut.'},
    'liver': {'keywords':('liver','detox','alcohol','hepat'),'penalize':('alcohol','beer','wine','high fructose'),'reason':'Alcohol and heavy additives add detox load.'},
}

def _http_get_json(url, timeout=12):
    req = urllib.request.Request(url, headers={'User-Agent': OFF_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))

def lookup_barcode(code):
    code = re.sub(r'\D+', '', code or '')
    if len(code) < 8:
        return None
    url = OFF_PRODUCT.format(code=code) + '?fields=code,product_name,brands,image_front_small_url,image_url,ingredients_text,ingredients_text_en,additives_tags,additives_n,nova_group,nutriscore_grade,nutrition_grades,labels_tags,allergens_tags,nutriments,quantity,categories'
    try:
        data = _http_get_json(url)
    except Exception:
        return None
    if not data or data.get('status') != 1 or not data.get('product'):
        return None
    return normalize_off_product(data['product'], data.get('code') or code)

def search_product_name(query):
    query = (query or '').strip()
    if len(query) < 3:
        return []
    params = urllib.parse.urlencode({'search_terms': query, 'search_simple': 1, 'action': 'process', 'json': 1, 'page_size': 8})
    try:
        data = _http_get_json(OFF_SEARCH + '?' + params)
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
        'nutrients': {'energy_kcal': num('energy-kcal_100g','energy-kcal'), 'sugars': num('sugars_100g','sugars'), 'salt': num('salt_100g','salt'), 'sodium': num('sodium_100g','sodium'), 'fat': num('fat_100g','fat'), 'sat_fat': num('saturated-fat_100g','saturated-fat'), 'fiber': num('fiber_100g','fiber'), 'protein': num('proteins_100g','proteins')},
    }

def client_flags_from_scan(raw_data):
    flags = set()
    text = (raw_data or '').lower() + ' ' + ' '.join(f.get('label','') for f in _parse_lines(raw_data or '')).lower()
    for flag, spec in PERSONAL_TRIGGERS.items():
        if any(k in text for k in spec['keywords']):
            flags.add(flag)
    return sorted(flags)

def score_product(product, personal_flags=None):
    personal_flags = set(personal_flags or [])
    nutrients = product.get('nutrients') or {}
    ingredients = (product.get('ingredients') or '').lower()
    labels = ' '.join(str(x) for x in (product.get('labels') or [])).lower()
    additives = product.get('additives') or []
    nutrition = 70
    sugars = nutrients.get('sugars')
    if sugars is not None:
        nutrition -= 28 if sugars >= 22 else 16 if sugars >= 12 else 8 if sugars >= 5 else 0
    sat = nutrients.get('sat_fat')
    if sat is not None:
        nutrition -= 16 if sat >= 10 else 8 if sat >= 5 else 0
    salt = nutrients.get('salt')
    if salt is None and nutrients.get('sodium') is not None:
        salt = nutrients['sodium'] * 2.5
    if salt is not None:
        nutrition -= 14 if salt >= 1.5 else 7 if salt >= 0.8 else 0
    fiber = nutrients.get('fiber') or 0
    protein = nutrients.get('protein') or 0
    if fiber >= 6: nutrition += 6
    elif fiber >= 3: nutrition += 3
    if protein >= 10: nutrition += 4
    nutrition = max(5, min(100, nutrition))
    additive_score = 80
    additive_hits = []
    for tag in additives:
        code = tag.replace('en:', '')
        penalty = ADDITIVE_PENALTY.get(code, 3)
        additive_score -= penalty
        if penalty >= 8:
            additive_hits.append(code.upper())
    nova = product.get('nova')
    if nova == 4: additive_score -= 18
    elif nova == 3: additive_score -= 8
    additive_score = max(5, min(100, additive_score))
    organic_bonus = 8 if ('organic' in labels or 'en:organic' in labels) else 0
    personal = 80
    personal_notes = []
    haystack = f"{ingredients} {product.get('name','')} {product.get('categories','')}".lower()
    for flag in personal_flags:
        spec = PERSONAL_TRIGGERS.get(flag)
        if not spec: continue
        hits = [word for word in spec['penalize'] if word in haystack]
        if hits:
            personal -= min(28, 8 * len(hits))
            personal_notes.append(spec['reason'] + ' Flagged: ' + ', '.join(hits[:4]) + '.')
    personal = max(5, min(100, personal))
    overall = int(round(max(1, min(100, 0.50*nutrition + 0.30*additive_score + 0.20*personal + organic_bonus*0.4))))
    if overall >= 75: band, label, color = 'good', 'Good match', '#1b7f4e'
    elif overall >= 50: band, label, color = 'ok', 'Okay in moderation', '#c9a227'
    elif overall >= 25: band, label, color = 'poor', 'Poor match', '#d35400'
    else: band, label, color = 'avoid', 'Better to skip', '#b03a2e'
    return {'score': overall, 'band': band, 'label': label, 'color': color, 'nutrition_score': int(nutrition), 'additive_score': int(additive_score), 'personal_score': int(personal), 'organic_bonus': organic_bonus, 'additive_hits': additive_hits[:8], 'personal_notes': personal_notes, 'personal_flags': sorted(personal_flags), 'nova': nova, 'nutriscore': product.get('nutriscore') or ''}

def extract_label_from_image(image_b64, mime='image/jpeg'):
    try:
        from health_advisor import _grok_vision_chat
    except Exception:
        return None
    prompt = 'Extract grocery label JSON only: {"barcode":"digits or null","name":"","brand":"","ingredients":"","sugars_100g":null,"salt_100g":null,"sat_fat_100g":null,"fiber_100g":null,"protein_100g":null,"additives":[],"organic":false}'
    raw = _grok_vision_chat([{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':f'data:{mime};base64,{image_b64}','detail':'high'}}], system='Return valid JSON only.', temperature=0.1, timeout=50)
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
    for src, dest in (('sugars_100g','sugars'),('salt_100g','salt'),('sat_fat_100g','sat_fat'),('fiber_100g','fiber'),('protein_100g','protein')):
        try:
            nutrients[dest] = float(extracted[src]) if extracted.get(src) is not None else None
        except (TypeError, ValueError):
            nutrients[dest] = None
    additives = []
    for item in extracted.get('additives') or []:
        text = str(item).lower()
        m = re.search(r'e\s*(\d{3,4}[a-z]?)', text)
        additives.append('e' + m.group(1) if m else text)
    return {'source':'label-photo','code': re.sub(r'\D+','', str(extracted.get('barcode') or '')),'name': (extracted.get('name') or 'Label photo').strip(),'brands': extracted.get('brand') or '','image':'','ingredients': extracted.get('ingredients') or '','additives': additives,'additives_n': len(additives),'nova': 4 if additives else None,'nutriscore':'','labels': ['en:organic'] if extracted.get('organic') else [],'allergens':[],'categories':'','quantity':'','nutrients': nutrients}

def scan_barcode_for_client(code, scan_raw=''):
    product = lookup_barcode(code)
    if not product:
        return {'ok': False, 'error': 'No product found for that barcode. Try a label photo.'}
    flags = client_flags_from_scan(scan_raw)
    return {'ok': True, 'product': product, 'rating': score_product(product, flags)}

def scan_photo_for_client(image_b64, mime='image/jpeg', scan_raw=''):
    extracted = extract_label_from_image(image_b64, mime)
    if not extracted:
        return {'ok': False, 'error': 'Could not read that label. Try a sharper photo or type the barcode.'}
    barcode = re.sub(r'\D+', '', str(extracted.get('barcode') or ''))
    product = lookup_barcode(barcode) if len(barcode) >= 8 else None
    if product is None:
        product = product_from_label_extract(extracted)
    if not product:
        return {'ok': False, 'error': 'Label was readable but not enough data to score.'}
    flags = client_flags_from_scan(scan_raw)
    return {'ok': True, 'product': product, 'rating': score_product(product, flags)}

def latest_scan_raw(reports):
    for report in reports or []:
        raw = getattr(report, 'raw_data', None) or ''
        if raw.strip():
            return raw
    return ''
