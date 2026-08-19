"""Emergency bootstrap: restore critical modules, load known-good app, apply upgrades."""
import os
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_GOOD_APP_COMMIT = "2a351976f5e927213c2b79722a1e4eb46ea429ec"
# Last known-good body_overview with Health Score charts
_GOOD_BODY_COMMIT = "edb2bbbfa6989a760fd4f2f2e01bf18f6cf05f4a"
_RAW = "https://raw.githubusercontent.com/Michaelpeatross/root-cause-website"


def _fetch(url, timeout=60):
    return urllib.request.urlopen(url, timeout=timeout).read().decode("utf-8")


def _restore_if_broken(filename, commit, min_bytes=5000):
    """Rewrite a local module from a known-good GitHub commit if it looks broken."""
    path = os.path.join(_HERE, filename)
    needs = True
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            if len(text) >= min_bytes and "def render_body_overview_html" in text:
                needs = False
        except Exception:
            needs = True
    if not needs:
        return
    url = f"{_RAW}/{commit}/{filename}"
    print(f"[Root Cause] Restoring {filename} from commit {commit[:8]}…")
    src = _fetch(url)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"[Root Cause] Restored {filename} ({len(src)} bytes)")


# Ensure body_overview is complete before any imports that depend on it
_restore_if_broken("body_overview.py", _GOOD_BODY_COMMIT, min_bytes=15000)

# Load last known-good full app.py
_URL = f"{_RAW}/{_GOOD_APP_COMMIT}/app.py"
_src = _fetch(_URL)
_path = os.path.join(_HERE, "_app_restored.py")
with open(_path, "w", encoding="utf-8") as _f:
    _f.write(_src)

exec(compile(_src, _path, "exec"), globals())

# Apply Health Age + PDF live upgrades
try:
    from report_live_upgrades import apply_report_upgrades
    apply_report_upgrades(app, db, Report, reports_dir)
except Exception as _upgrade_err:
    print(f"[Root Cause] Live upgrades not applied: {_upgrade_err}")
