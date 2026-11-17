"""Cloudflare Web Analytics beacon is on every public HTML page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates'
TOKEN = '12b0ff074f364a12be306335b118b8fe'
BEACON = 'https://static.cloudflareinsights.com/beacon.min.js'
INCLUDE = "{% include '_cf_web_analytics.html' %}"

# Full pages that do not extend base.html and must include the beacon themselves.
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


def test_base_and_standalone_pages_include_snippet():
    missing = []
    for name in ['base.html', *STANDALONE_PAGES]:
        text = (TEMPLATES / name).read_text()
        if INCLUDE not in text:
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
