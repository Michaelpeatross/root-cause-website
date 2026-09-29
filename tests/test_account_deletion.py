"""Account deletion flow (Guideline 5.1.1(v)). Run: python -m pytest tests -q"""
import os, sys, tempfile
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
flask = pytest.importorskip('flask')
fsa = pytest.importorskip('flask_sqlalchemy')
from werkzeug.security import generate_password_hash  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    tpl = tmp_path / 'tpl'; tpl.mkdir()
    (tpl / 'base.html').write_text('<html><body>{% block content %}{% endblock %}</body></html>')
    app = flask.Flask(__name__, template_folder=str(tpl))
    app.config.update(SECRET_KEY='t', SQLALCHEMY_DATABASE_URI='sqlite://', TESTING=True)
    db = fsa.SQLAlchemy(app)

    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True); email = db.Column(db.String(120), unique=True)
        password = db.Column(db.String(200)); is_admin = db.Column(db.Boolean, default=False)

    class Report(db.Model):
        id = db.Column(db.Integer, primary_key=True); user_email = db.Column(db.String(120)); pdf_filename = db.Column(db.String(200))

    class ClientDocument(db.Model):
        id = db.Column(db.Integer, primary_key=True); user_email = db.Column(db.String(120)); stored_filename = db.Column(db.String(200))

    class ReportScanPdf(db.Model):
        id = db.Column(db.Integer, primary_key=True); report_id = db.Column(db.Integer); stored_filename = db.Column(db.String(200))

    docs = tmp_path / 'docs'; docs.mkdir(); (docs / 'a.pdf').write_text('x')
    import food_scan_history, food_diary
    monkeypatch.setattr(food_scan_history, 'HISTORY_DIR', str(tmp_path / 'scans'))
    monkeypatch.setattr(food_diary, 'DIARY_DIR', str(tmp_path / 'diary'))
    from account_deletion import register_account_deletion_routes
    register_account_deletion_routes(app, db, User, Report, ClientDocument, ReportScanPdf, str(docs), str(tmp_path))

    @app.route('/dashboard')
    def dashboard():
        return '<html><body><p>Your personalized bioenergetic portal</p></body></html>'

    with app.app_context():
        db.create_all()
        u = User(email='a@b.com', password=generate_password_hash('pw')); db.session.add(u)
        r = Report(user_email='a@b.com'); db.session.add(r); db.session.flush()
        db.session.add(ReportScanPdf(report_id=r.id, stored_filename='a.pdf'))
        db.session.add(ClientDocument(user_email='a@b.com', stored_filename='missing.pdf'))
        db.session.commit()
        food_scan_history.save_scan('a@b.com', {'product': {'name': 'Apple'}, 'rating': {'score': 100}})
        food_diary.save_meal('a@b.com', {'name': 'Apple'})
        yield app, db, User, Report, ClientDocument, docs, food_scan_history, food_diary, u.id


def _login(client, uid):
    with client.session_transaction() as s:
        s['user_id'] = uid; s['email'] = 'a@b.com'


def test_requires_login(env):
    app = env[0]
    assert app.test_client().get('/account/delete').status_code == 302


def test_wrong_password_keeps_account(env):
    app, db, User, *_rest, uid = env
    c = app.test_client(); _login(c, uid)
    r = c.post('/account/delete', data={'password': 'nope', 'confirm': 'DELETE'})
    assert b'not correct' in r.data
    with app.app_context():
        assert User.query.count() == 1


def test_delete_removes_everything(env):
    app, db, User, Report, ClientDocument, docs, hist, diary, uid = env
    c = app.test_client(); _login(c, uid)
    r = c.post('/account/delete', data={'password': 'pw', 'confirm': 'delete'})
    assert b'has been deleted' in r.data
    with app.app_context():
        assert User.query.count() == 0 and Report.query.count() == 0 and ClientDocument.query.count() == 0
    assert not (docs / 'a.pdf').exists()
    assert hist.load_history('a@b.com') == [] and diary.load_meals('a@b.com') == []
    with c.session_transaction() as s:
        assert 'user_id' not in s


def test_dashboard_shows_delete_link(env):
    app, *_rest, uid = env
    c = app.test_client(); _login(c, uid)
    assert b'href="/account/delete"' in c.get('/dashboard').data
