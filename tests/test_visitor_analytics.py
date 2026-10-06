"""Visitor analytics: page-view logging, bot skip, no raw IP, auth on stats."""
import json
import os
import sqlite3
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
flask = pytest.importorskip('flask')
pytest.importorskip('sqlalchemy')

UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1')


class _User(object):
    def __init__(self, admin):
        self.is_admin = admin


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv('RC_ANALYTICS_SYNC', '1')
    monkeypatch.delenv('ANALYTICS_API_TOKEN', raising=False)
    app = flask.Flask(__name__, root_path=os.path.dirname(HERE))
    app.secret_key = 't'

    @app.route('/')
    def index():
        return '<html><head></head><body>home</body></html>'

    @app.route('/buy')
    def buy():
        return '<html><head></head><body>order</body></html>'

    @app.route('/static/x.css')
    def css():
        return 'body{}', 200, {'Content-Type': 'text/css'}

    @app.route('/create-checkout-session', methods=['POST'])
    def checkout():
        return flask.redirect('https://checkout.stripe.com/c/pay/abc', 303)

    def current_user():
        return _User(True) if flask.session.get('is_admin') else None

    from visitor_analytics import register_visitor_analytics
    db = tmp_path / 'analytics.db'
    store = register_visitor_analytics(app, get_current_user=current_user,
                                       db_url='sqlite:///%s' % db,
                                       salt_path=str(tmp_path / 'salt.txt'))
    return app, store, str(db)


def test_pageview_logged_without_raw_ip(tmp_path, monkeypatch):
    app, store, db = _make_app(tmp_path, monkeypatch)
    c = app.test_client()
    r = c.get('/?utm_source=twitter&utm_campaign=launch',
              headers={'User-Agent': UA, 'Referer': 'https://t.co/xyz', 'X-Forwarded-For': '203.0.113.9'})
    assert r.status_code == 200
    assert '__rcpv' in r.get_data(as_text=True)
    cookies = r.headers.getlist('Set-Cookie')
    assert any(h.startswith('rc_vid=') for h in cookies)
    assert any(h.startswith('rc_sid=') for h in cookies)
    c.get('/static/x.css', headers={'User-Agent': UA})
    c.get('/', headers={'User-Agent': 'Googlebot/2.1 (+http://www.google.com/bot.html)'})
    con = sqlite3.connect(db)
    rows = con.execute('select path, source, utm_campaign, device, os, ip_hash from rc_visit_event').fetchall()
    assert rows == [('/', 'x', 'launch', 'mobile', 'iOS', rows[0][5])]
    dump = json.dumps(con.execute('select * from rc_visit_event').fetchall())
    assert '203.0.113.9' not in dump
    assert con.execute('select bot, hits from rc_bot_daily').fetchall() == [('Googlebot', 1)]


def test_funnel_events_and_stats_auth(tmp_path, monkeypatch):
    app, store, db = _make_app(tmp_path, monkeypatch)
    c = app.test_client()
    c.get('/', headers={'User-Agent': UA})
    c.get('/buy', headers={'User-Agent': UA})
    c.post('/create-checkout-session', data={'product': 'single'}, headers={'User-Agent': UA})
    assert c.get('/admin/stats.json').status_code == 401
    monkeypatch.setenv('ANALYTICS_API_TOKEN', 'x' * 24)
    assert c.get('/admin/stats.json', headers={'Authorization': 'Bearer wrong-wrong-wrong-1'}).status_code == 401
    r = c.get('/admin/stats.json', headers={'Authorization': 'Bearer ' + 'x' * 24})
    assert r.status_code == 200
    data = r.get_json()
    steps = {s['step']: s['visitors'] for s in data['funnel']}
    assert steps['Landed (any page)'] == 1
    assert steps['Viewed order page (/buy)'] == 1
    assert steps['Clicked checkout'] == 1
    assert steps['Redirected to Stripe'] == 1
    assert data['summary']['today']['pageviews'] == 2


def test_admin_visits_marked_internal(tmp_path, monkeypatch):
    app, store, db = _make_app(tmp_path, monkeypatch)
    c = app.test_client()
    with c.session_transaction() as s:
        s['is_admin'] = True
    c.get('/', headers={'User-Agent': UA})
    data = c.get('/admin/stats.json').get_json()
    assert data['summary']['today']['pageviews'] == 0
    assert c.get('/admin/stats.json?include_internal=1').get_json()['summary']['today']['pageviews'] == 1


def test_tag_defaults_and_env_override(monkeypatch):
    import visitor_analytics as va
    monkeypatch.delenv('GA_MEASUREMENT_ID', raising=False)
    assert va._tag_value('GA_MEASUREMENT_ID') == 'G-HTF90RE438'
    monkeypatch.setenv('GA_MEASUREMENT_ID', 'G-OTHER12345')
    assert va._tag_value('GA_MEASUREMENT_ID') == 'G-OTHER12345'
    monkeypatch.setenv('GA_MEASUREMENT_ID', 'off')
    assert va._tag_value('GA_MEASUREMENT_ID') == ''
    monkeypatch.delenv('CLARITY_PROJECT_ID', raising=False)
    assert va._tag_value('CLARITY_PROJECT_ID') == ''
