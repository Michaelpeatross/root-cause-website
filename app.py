"""Emergency bootstrap: load last known-good app.py, then apply live upgrades."""
import os
import urllib.request

_GOOD_COMMIT = "2a351976f5e927213c2b79722a1e4eb46ea429ec"
_URL = (
    "https://raw.githubusercontent.com/Michaelpeatross/root-cause-website/"
    f"{_GOOD_COMMIT}/app.py"
)

_src = urllib.request.urlopen(_URL, timeout=60).read().decode("utf-8")
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_app_restored.py")
with open(_path, "w", encoding="utf-8") as _f:
    _f.write(_src)

exec(compile(_src, _path, "exec"), globals())

# Apply Health Scores + on-demand PDF upgrades for existing reports
try:
    from report_live_upgrades import apply_report_upgrades
    apply_report_upgrades(app, db, Report, reports_dir)
except Exception as _upgrade_err:
    print(f"[Root Cause] Live upgrades not applied: {_upgrade_err}")
