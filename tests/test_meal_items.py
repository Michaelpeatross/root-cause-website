"""Itemized meal photos: per-item rows, eaten/share math, edits, save without duplicates."""
import json, os, subprocess, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
flask = pytest.importorskip('flask')

import meal_items  # noqa: E402

TABLE_PHOTO = {
    'name': 'Shared appetizer table', 'people': 3,
    'items': [
        {'name': 'Tortilla chips', 'portion': '1 basket', 'grams': 90, 'calories': 440, 'protein_g': 6, 'carbs_g': 57,
         'fat_g': 21, 'processing': 'processed', 'fried': True, 'shared': True, 'partly_eaten': True},
        {'name': 'Salsa', 'portion': '1 small bowl', 'grams': 120, 'calories': 40, 'protein_g': 2, 'carbs_g': 8,
         'fat_g': 0, 'processing': 'minimal', 'shared': True},
        {'name': 'Queso dip', 'portion': '1 small bowl', 'grams': 120, 'calories': 260, 'protein_g': 8, 'carbs_g': 10,
         'fat_g': 21, 'processing': 'processed', 'shared': True},
        {'name': 'Baked potato', 'portion': '1 large', 'grams': 300, 'calories': 280, 'protein_g': 7, 'carbs_g': 63,
         'fat_g': 0.4, 'processing': 'whole'},
        {'name': 'Side salad', 'portion': '1 bowl', 'grams': 150, 'calories': 30, 'protein_g': 2, 'carbs_g': 5,
         'fat_g': 0.3, 'processing': 'whole'},
    ],
    'notes': 'A shared table with chips, dips, a potato and a salad.',
}


def test_match_and_lookup_food_table():
    assert meal_items.match_food('Basket of tortilla chips') == 'tortilla chips'
    assert meal_items.match_food('Loaded baked potato') == 'loaded baked potato'
    assert meal_items.match_food('queso') == 'queso dip'
    assert meal_items.match_food('mystery stew') is None
    item = meal_items.lookup_food('guac')
    assert item['matched'] == 'guacamole' and item['base']['calories'] > 50
    names = [s['name'] for s in meal_items.search_foods('sal')]
    assert 'Salsa' in names


def test_totals_respect_eaten_share_size_and_meal_split():
    a = meal_items.make_item({'name': 'Baked potato', 'calories': 200, 'protein_g': 4})
    b = meal_items.make_item({'name': 'Tortilla chips', 'calories': 400, 'protein_g': 6})
    c = meal_items.make_item({'name': 'Soda', 'calories': 150})
    c['eaten'] = False  # unchecked -> not counted
    t = meal_items.compute_totals([a, b, c], 1)
    assert t['calories'] == 600 and t['items_eaten'] == 2
    # Per-item share
    b['share'], b['share_override'] = 0.25, True
    assert meal_items.compute_totals([a, b, c], 1)['calories'] == 300
    # Meal split applies to items without their own override
    assert meal_items.compute_totals([a, b, c], 2)['calories'] == 200  # 200/2 + 400/4
    # Size multiplier
    a['size'] = 1.5
    assert meal_items.compute_totals([a], 1)['calories'] == 300
    # Score is calorie-weighted over eaten items only
    assert meal_items.compute_totals([c], 1)['score'] is None


def test_js_and_python_math_agree():
    items = [
        {'base': {'calories': 440, 'protein': 6, 'fat': 21}, 'score': 50, 'share': 1 / 3, 'share_override': True, 'eaten': True, 'size': 1},
        {'base': {'calories': 280, 'protein': 7, 'fat': 0.4}, 'score': 100, 'eaten': True, 'size': 1.5, 'share': 1},
        {'base': {'calories': 260, 'protein': 8, 'fat': 21}, 'score': 60, 'eaten': False, 'share': 1},
        {'base': {'calories': 30, 'protein': 2}, 'score': 100, 'share': 0.5, 'share_override': True, 'eaten': True, 'size': 2},
    ]
    script = ("const L=require(%s);const items=%s;const out={};"
              "[1,2,3].forEach(function(s){out[s]=L.computeTotals(items,s);});"
              "out.pct=L.parsePercent('35%%');out.key=L.shareKey(items[0],1);"
              "process.stdout.write(JSON.stringify(out));") % (json.dumps(os.path.join(ROOT, 'static', 'js', 'meal_logic.js')), json.dumps(items))
    js = json.loads(subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True).stdout)
    for split in (1, 2, 3):
        py = meal_items.compute_totals(items, split)
        assert js[str(split)]['calories'] == py['calories']
        assert js[str(split)]['score'] == py['score']
        assert abs(js[str(split)]['protein'] - py['protein']) < 0.11
    assert js['pct'] == 0.35 and js['key'] == '1/3'


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    import food_diary, food_scan_history, meal_photo
    monkeypatch.setattr(food_diary, 'DIARY_DIR', str(tmp_path / 'diary'))
    monkeypatch.setattr(food_scan_history, 'HISTORY_DIR', str(tmp_path / 'scans'))
    monkeypatch.setattr(meal_photo, '_vision', lambda b, m: json.loads(json.dumps(TABLE_PHOTO)))
    monkeypatch.setattr(meal_photo, 'estimate_food_text', lambda name, portion='': None)
    app = flask.Flask(__name__, root_path=ROOT)
    app.secret_key = 't'
    from food_scan_routes import register_food_scan_routes
    register_food_scan_routes(app)
    return app.test_client()


def _login(c, email='meal@test.com'):
    with c.session_transaction() as s:
        s['email'] = email


def test_table_photo_is_split_into_items_and_not_auto_saved(app_client):
    c = app_client
    _login(c)
    r = c.post('/api/food-scan/meal', json={'image_b64': 'A' * 200}).get_json()
    assert r['ok'] and r['kind'] == 'meal' and r['saved'] is False
    names = [i['name'] for i in r['items']]
    assert names == ['Tortilla chips', 'Salsa', 'Queso dip', 'Baked potato', 'Side salad']
    assert r['people'] == 3 and r['shared_table'] is True
    chips = r['items'][0]
    assert chips['partly_eaten'] and chips['shared_dish'] and chips['share_override']
    assert abs(chips['share'] - 1 / 3) < 0.001
    assert all(i['score'] is not None and i['label'] for i in r['items'])
    assert r['photo_key']
    # Nothing in today's intake until Save meal.
    d = c.get('/api/food-scan/diary').get_json()
    assert d['today']['meals'] == 0


def test_save_meal_once_and_no_duplicates(app_client):
    c = app_client
    _login(c)
    r = c.post('/api/food-scan/meal', json={'image_b64': 'A' * 200}).get_json()
    items = r['items']
    items[4]['eaten'] = False                     # didn't eat the salad
    items[3]['share'], items[3]['share_override'] = 0.5, True   # half the potato
    items[0]['name'] = 'Corn chips'               # renamed
    body = {'items': items, 'meal_split': 1, 'save_id': 'abc123', 'photo_key': r['photo_key']}
    s1 = c.post('/api/food-scan/meal/save', json=body).get_json()
    assert s1['ok'] and s1['saved'] and not s1['replaced']
    expected = round(440 / 3 + 40 / 3 + 260 / 3 + 280 * 0.5)
    assert abs(s1['totals']['calories'] - expected) <= 1
    assert s1['meal']['items'][0]['name'] == 'Corn chips'
    # Double tap: same save_id -> updated, not added
    s2 = c.post('/api/food-scan/meal/save', json=body).get_json()
    assert s2['ok'] and s2['replaced'] and s2['meal']['id'] == s1['meal']['id']
    # Re-estimate of the same photo (new save_id, same photo_key) -> still one entry
    body3 = dict(body, save_id='zzz999')
    s3 = c.post('/api/food-scan/meal/save', json=body3).get_json()
    assert s3['replaced']
    d = c.get('/api/food-scan/diary').get_json()
    assert d['today']['meals'] == 1
    assert d['today']['calories'] == s1['totals']['calories']


def test_edit_and_delete_intake_entries(app_client):
    c = app_client
    _login(c)
    r = c.post('/api/food-scan/meal', json={'image_b64': 'A' * 200}).get_json()
    s1 = c.post('/api/food-scan/meal/save', json={'items': r['items'], 'save_id': 'x1', 'photo_key': 'p1'}).get_json()
    entry_id = s1['meal']['id']
    # Reopen and edit the items: uncheck everything but the potato
    items = s1['meal']['items']
    for it in items:
        it['eaten'] = it['name'] == 'Baked potato'
    e = c.post('/api/food-scan/meal/save', json={'items': items, 'entry_id': entry_id, 'save_id': 'x1'}).get_json()
    assert e['ok'] and e['meal']['id'] == entry_id and e['meal']['calories'] == 280
    # Quick edit: rename + "I had half"
    u = c.post('/api/food-scan/diary/update', json={'id': entry_id, 'name': 'Potato', 'scale': 0.5}).get_json()
    assert u['ok'] and u['meal']['name'] == 'Potato' and u['meal']['calories'] == 140
    dl = c.post('/api/food-scan/diary/delete', json={'id': entry_id}).get_json()
    assert dl['ok'] and dl['today']['meals'] == 0
    assert c.post('/api/food-scan/diary/delete', json={'id': entry_id}).get_json()['ok'] is False


def test_guest_can_save_without_account(app_client):
    c = app_client
    r = c.post('/api/food-scan/meal', json={'image_b64': 'A' * 200}).get_json()
    assert r['guest'] is True
    s = c.post('/api/food-scan/meal/save', json={'items': r['items'], 'save_id': 'g1'}).get_json()
    assert s['ok'] and s['guest'] and s['saved'] is False and s['meal']['calories'] > 0
    assert c.post('/api/food-scan/diary/delete', json={'id': 'x'}).status_code == 401
    nothing = c.post('/api/food-scan/meal/save', json={'items': [dict(r['items'][0], eaten=False)]}).get_json()
    assert nothing['ok'] is False


def test_rename_relookup_and_autocomplete(app_client):
    c = app_client
    r = c.post('/api/food-scan/meal/item', json={'name': 'guacamole', 'id': 'keep1', 'share': 0.5, 'share_override': True}).get_json()
    assert r['ok'] and r['item']['id'] == 'keep1' and r['item']['base']['calories'] > 50
    assert r['item']['share'] == 0.5 and r['item']['source'] == 'database'
    miss = c.post('/api/food-scan/meal/item', json={'name': 'grandma special'}).get_json()
    assert miss['ok'] is False
    f = c.get('/api/food-scan/foods?q=que').get_json()
    assert f['ok'] and f['items'][0]['name'] == 'Queso dip'


def test_old_vision_format_still_works(monkeypatch):
    import meal_photo
    monkeypatch.setattr(meal_photo, '_vision', lambda b, m: {'name': 'Eggs and berries', 'calories': 400, 'components': [
        {'name': 'eggs', 'processing': 'minimal', 'share': 0.75}, {'name': 'blueberries', 'processing': 'whole', 'share': 0.25}]})
    out = meal_photo.analyze_plate_for_client('A' * 200)
    assert out['ok'] and [i['name'] for i in out['items']] == ['Eggs', 'Blueberries']
    assert out['items'][0]['base']['calories'] == 300 and out['totals']['calories'] == 400


def test_label_photo_is_not_auto_added_to_intake(app_client, monkeypatch):
    import food_scanner
    c = app_client
    _login(c)
    monkeypatch.setattr(food_scanner, 'scan_photo_for_client', lambda b, mime='', scan_raw='': {
        'ok': True, 'product': {'name': 'Crackers', 'nutrients': {'energy_kcal': 120}}, 'rating': {'score': 40, 'label': 'x'}})
    r = c.post('/api/food-scan/photo', json={'image_b64': 'A' * 200}).get_json()
    assert r['ok'] and r['saved'] is False
    assert c.get('/api/food-scan/diary').get_json()['today']['meals'] == 0
