"""Tongue Scanner: page renders, bad uploads rejected, report built, history saved for logged-in users."""
import os, sys
import pytest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
flask = pytest.importorskip('flask')

IMG = 'data:image/jpeg;base64,' + 'A' * 400
GOOD = {'is_tongue': True, 'quality': 'good', 'body_color': 'pink', 'coating_thickness': 'thick',
        'coating_color': 'yellow', 'swelling': 'mild', 'tooth_marks': 'noticeable', 'thin_body': False,
        'cracks': 'few', 'red_dots': False, 'moisture': 'dry', 'tip_red': True, 'spot_of_concern': False,
        'summary': 'A pink tongue with a yellowish coating toward the back.'}


def _app(tmp_path, monkeypatch):
    import tongue_scan
    monkeypatch.setattr(tongue_scan, 'HISTORY_DIR', str(tmp_path))
    app = flask.Flask(__name__, root_path=os.path.dirname(HERE))
    app.secret_key = 't'
    for ep in ('index', 'buy', 'login', 'register', 'dashboard', 'logout', 'admin'):
        app.add_url_rule('/' + ep, ep, lambda: 'x')
    tongue_scan.register_tongue_scan_routes(app)
    return app, tongue_scan


def test_page_renders(tmp_path, monkeypatch):
    app, _ = _app(tmp_path, monkeypatch)
    c = app.test_client()
    for path in ('/tongue-scanner', '/health-app/tongue-scanner'):
        r = c.get(path)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Tongue Scanner' in html and 'capture="user"' in html and '15 minutes' in html
        body = html[html.index('<h1>Tongue Scanner'):]
        body = body[:body.index('</script>')]
        assert 'grok' not in body.lower() and ' AI ' not in body and 'Covington' not in html


def test_bad_uploads(tmp_path, monkeypatch):
    app, ts = _app(tmp_path, monkeypatch)
    c = app.test_client()
    assert c.post('/api/tongue-scan', json={}).status_code == 400
    assert c.post('/api/tongue-scan', json={'image_b64': 'data:application/pdf;base64,' + 'A' * 400}).status_code == 400
    assert c.post('/api/tongue-scan', json={'image_b64': '<script>' * 100}).status_code == 400
    r = c.post('/api/tongue-scan', data='not json', content_type='text/plain')
    assert r.status_code == 400
    monkeypatch.setattr(ts, '_vision', lambda b, m: {'is_tongue': False})
    d = c.post('/api/tongue-scan', json={'image_b64': IMG}).get_json()
    assert not d['ok'] and d['not_tongue']
    monkeypatch.setattr(ts, '_vision', lambda b, m: {'is_tongue': True, 'quality': 'poor'})
    d = c.post('/api/tongue-scan', json={'image_b64': IMG}).get_json()
    assert not d['ok'] and d['retake']
    monkeypatch.setattr(ts, '_vision', lambda b, m: None)
    d = c.post('/api/tongue-scan', json={'image_b64': IMG}).get_json()
    assert not d['ok']


def test_guest_report_not_saved(tmp_path, monkeypatch):
    app, ts = _app(tmp_path, monkeypatch)
    monkeypatch.setattr(ts, '_vision', lambda b, m: dict(GOOD))
    d = app.test_client().post('/api/tongue-scan', json={'image_b64': IMG}).get_json()
    assert d['ok'] and not d['saved']
    assert [x['label'] for x in d['dimensions']] == ['Body color', 'Coating color', 'Coating', 'Shape', 'Surface']
    assert 0 < d['overall'] < 100
    assert 'Thick Yellow Coating' in d['tags'] and 'Tooth-mark edges' in d['tags']
    assert any(s['title'] == 'Hydration' for s in d['suggestions'])
    assert 'not medical advice' in d['disclaimer'].lower()
    assert os.listdir(tmp_path) == []


def test_logged_in_history(tmp_path, monkeypatch):
    app, ts = _app(tmp_path, monkeypatch)
    monkeypatch.setattr(ts, '_vision', lambda b, m: dict(GOOD))
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = 1
        s['email'] = 'A@x.com'
    d = c.post('/api/tongue-scan', json={'image_b64': IMG, 'thumb': 'data:image/jpeg;base64,AAAA'}).get_json()
    assert d['saved']
    h = c.get('/api/tongue-scan/history').get_json()
    assert len(h['items']) == 1 and h['items'][0]['overall'] == d['overall']
    assert c.post('/api/tongue-scan/history/delete', json={'id': h['items'][0]['id']}).get_json()['ok']
    assert c.get('/api/tongue-scan/history').get_json()['items'] == []


def test_typical_tongue_scores_high():
    import tongue_scan
    r = tongue_scan.build_report({'body_color': 'light red', 'coating_thickness': 'thin', 'coating_color': 'white'})
    assert r['overall'] == 100 and r['band'] == 'Well balanced'
    r = tongue_scan.build_report({'summary': 'Our AI model says this', 'spot_of_concern': True})
    assert r['summary'] == '' and 'care_note' in r
