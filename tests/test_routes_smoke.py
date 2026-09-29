"""Smoke test: scanner API routes return the new rating fields (network stubbed)."""
import os, sys
import pytest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
flask = pytest.importorskip('flask')


def test_barcode_and_plate_routes(monkeypatch):
    import food_scanner, meal_photo
    monkeypatch.setattr(food_scanner, 'lookup_barcode', lambda code: {'name': 'Raw almonds', 'ingredients': 'almonds', 'nutrients': {'fat': 50}, 'additives': [], 'labels': []})
    monkeypatch.setattr(meal_photo, '_vision', lambda b, m: {'name': 'Eggs and berries', 'calories': 350, 'components': [
        {'name': 'fried eggs', 'processing': 'minimal', 'share': 0.5}, {'name': 'blueberries', 'processing': 'whole', 'share': 0.5}]})
    app = flask.Flask(__name__, root_path=os.path.dirname(HERE))
    app.secret_key = 't'
    from food_scan_routes import register_food_scan_routes
    register_food_scan_routes(app)
    c = app.test_client()
    r = c.post('/api/food-scan/barcode', json={'barcode': '0123456789012'}).get_json()
    assert r['ok'] and r['rating']['score'] == 100 and r['rating']['processing_tier'] == '1'
    r = c.post('/api/food-scan/meal', json={'image_b64': 'A' * 200}).get_json()
    assert r['ok'] and r['rating']['score'] >= 90
