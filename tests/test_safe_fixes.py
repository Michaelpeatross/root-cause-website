"""Safe/mechanical website fixes: contrast color, favicon, security headers, landmarks, canonical."""
import os, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
flask = pytest.importorskip('flask')


def test_green_contrast_token():
    css = open(os.path.join(ROOT, 'static/css/site.css'), encoding='utf-8').read()
    assert '--green: #198574;' in css
    assert '--green: #1a8c7a;' not in css
    assert "@import url('https://fonts.googleapis.com" not in css


def test_base_template_landmarks_fonts_favicon():
    text = open(os.path.join(ROOT, 'templates/base.html'), encoding='utf-8').read()
    assert '<main id="main">' in text and '</main>' in text
    assert 'rel="preconnect" href="https://fonts.googleapis.com"' in text
    assert 'rel="preconnect" href="https://fonts.gstatic.com"' in text
    assert 'rel="preload" as="style"' in text
    assert 'family=Inter' in text and 'display=swap' in text
    assert 'href="/favicon.ico"' in text


def test_footer_heading_is_not_h4():
    footer = open(os.path.join(ROOT, 'templates/_site_footer.html'), encoding='utf-8').read()
    assert '<h4>' not in footer
    assert 'class="footer-heading"' in footer
    import seo_routes
    src = open(seo_routes.__file__, encoding='utf-8').read() if hasattr(seo_routes, '__file__') else ''
    # The injected footer lives in seo_routes.py
    seo = open(os.path.join(ROOT, 'seo_routes.py'), encoding='utf-8').read()
    assert '<p class="footer-heading">Product</p>' in seo
    assert '<h4>Product</h4>' not in seo


def test_tongue_template_has_canonical():
    text = open(os.path.join(ROOT, 'templates/tongue_scanner.html'), encoding='utf-8').read()
    assert 'rel="canonical"' in text
    assert 'www.root-cause-test.com{{ request.path }}' in text


def _app():
    app = flask.Flask(__name__, root_path=ROOT, static_folder=os.path.join(ROOT, 'static'),
                      template_folder=os.path.join(ROOT, 'templates'))
    app.secret_key = 't'
    for ep, path in [('index', '/'), ('buy', '/buy'), ('login', '/login'), ('register', '/register'),
                     ('dashboard', '/dashboard'), ('logout', '/logout'), ('admin', '/admin'),
                     ('contact', '/contact'), ('privacy', '/privacy'), ('terms', '/terms'),
                     ('refunds', '/refunds'), ('health_app', '/health-app')]:
        # unique endpoints; some will be overwritten by seo_routes
        if ep not in app.view_functions:
            app.add_url_rule(path, ep, lambda: 'x')
    from seo_routes import register_public_seo_routes
    register_public_seo_routes(app)
    import tongue_scan
    tongue_scan.register_tongue_scan_routes(app)
    return app


def test_security_headers_and_favicon():
    app = _app()
    c = app.test_client()
    r = c.get('/privacy')
    assert r.status_code == 200
    assert r.headers.get('Strict-Transport-Security') == 'max-age=31536000'
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert r.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
    assert 'camera=(self)' in r.headers.get('Permissions-Policy', '')
    assert 'Content-Security-Policy' not in r.headers
    ico = c.get('/favicon.ico')
    assert ico.status_code == 200
    assert 'image' in (ico.headers.get('Content-Type') or '')
    assert len(ico.data) > 16


def test_tongue_scanner_canonical_and_main():
    app = _app()
    c = app.test_client()
    r = c.get('/tongue-scanner')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'rel="canonical"' in html
    assert 'https://www.root-cause-test.com/tongue-scanner' in html
    assert '<main id="main">' in html
    # Cloudflare beacon must remain
    assert 'static.cloudflareinsights.com/beacon.min.js' in html
    assert '12b0ff074f364a12be306335b118b8fe' in html
