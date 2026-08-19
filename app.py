"""Bootstrap: inject good body_overview into memory, load known-good app, apply upgrades."""
import os
import sys
import types
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_GOOD_APP_COMMIT = "2a351976f5e927213c2b79722a1e4eb46ea429ec"
_GOOD_BODY_COMMIT = "edb2bbbfa6989a760fd4f2f2e01bf18f6cf05f4a"
_RAW = "https://raw.githubusercontent.com/Michaelpeatross/root-cause-website"


def _fetch(url, timeout=60):
    return urllib.request.urlopen(url, timeout=timeout).read().decode("utf-8")


def _ensure_body_overview():
    """Load a known-good body_overview into sys.modules (works on read-only deploys)."""
    existing = sys.modules.get("body_overview")
    if existing is not None and hasattr(existing, "render_body_overview_html"):
        return
    # Local file might be truncated from a bad push — ignore if incomplete
    local = os.path.join(_HERE, "body_overview.py")
    src = None
    if os.path.isfile(local):
        try:
            with open(local, "r", encoding="utf-8") as f:
                text = f.read()
            if len(text) >= 15000 and "def render_body_overview_html" in text:
                src = text
        except Exception:
            pass
    if src is None:
        url = f"{_RAW}/{_GOOD_BODY_COMMIT}/body_overview.py"
        print(f"[Root Cause] Loading body_overview from commit {_GOOD_BODY_COMMIT[:8]}…")
        src = _fetch(url)
        print(f"[Root Cause] Loaded body_overview ({len(src)} bytes)")
    mod = types.ModuleType("body_overview")
    mod.__file__ = local
    exec(compile(src, local, "exec"), mod.__dict__)
    sys.modules["body_overview"] = mod


_ensure_body_overview()

# Load last known-good full app.py
_URL = f"{_RAW}/{_GOOD_APP_COMMIT}/app.py"
_src = _fetch(_URL)
_path = os.path.join(_HERE, "_app_restored.py")
try:
    with open(_path, "w", encoding="utf-8") as _f:
        _f.write(_src)
except Exception:
    # Read-only filesystem — exec from memory
    _path = "<app_restored>"

exec(compile(_src, _path, "exec"), globals())

# Apply Health Age + PDF live upgrades
try:
    from report_live_upgrades import apply_report_upgrades
    apply_report_upgrades(app, db, Report, reports_dir)
except Exception as _upgrade_err:
    print(f"[Root Cause] Live upgrades not applied: {_upgrade_err}")
    import traceback
    traceback.print_exc()
