"""Cloudflare Web Analytics beacon is on every public HTML page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates'
TOKEN = '12b0ff074f364a12be306335b118b8fe'
BEACON = 'https://static.cloudflareinsights.com/beacon.min.js'
INCLUDE = "{% include '_cf_web_analytics.html' %}"

# These pages are served as raw HTML (not Jinja), so the snippet must be inlined.
STANDALONE_PAGES = [
    'agency.html',
    'ai_transformation.html',
    'business.html',
    'foam.html',
    'house_plans.html',
    'k12_scholarships.html',
]


def test_shared_snippet_has_official_beacon():
    snippet = (TEMPLATES / '_cf_web_analytics.html').read_text()
    assert BEACON in snippet
    assert TOKEN in snippet
    assert 'data-cf-beacon' in snippet


def test_base_template_includes_shared_snippet():
    text = (TEMPLATES / 'base.html').read_text()
    assert INCLUDE in text
    # Token lives in the include so it stays in one place for Jinja pages.
    assert TOKEN not in text


def test_standalone_static_pages_inline_the_beacon():
    missing = []
    for name in STANDALONE_PAGES:
        text = (TEMPLATES / name).read_text()
        if BEACON not in text or TOKEN not in text or INCLUDE in text:
            missing.append(name)
    assert missing == []


def test_partials_do_not_duplicate_beacon():
    extras = []
    for path in TEMPLATES.rglob('*.html'):
        if path.name in {'base.html', '_cf_web_analytics.html', *STANDALONE_PAGES}:
            continue
        text = path.read_text()
        if BEACON in text or '_cf_web_analytics.html' in text:
            extras.append(path.relative_to(TEMPLATES).as_posix())
    assert extras == []
