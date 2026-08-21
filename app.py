"""Bootstrap: inject good body_overview, harden scan PDF uploads, load app, apply upgrades."""
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


def _patch_scan_pdf_uploads():
    """Replace process_scan_pdf_uploads with a crash-safe version for large imaging PDFs."""
    try:
        import document_service as ds
    except Exception as exc:
        print(f"[Root Cause] document_service import failed: {exc}")
        return

    SCAN_PDF_MAX_BYTES = 40 * 1024 * 1024

    def process_scan_pdf_uploads(file_list, upload_dir):
        import os
        import uuid
        import traceback
        from werkzeug.utils import secure_filename

        if not file_list:
            return [], []

        results = []
        errors = []
        for file_storage in file_list:
            if not file_storage or not file_storage.filename:
                continue
            original = secure_filename(file_storage.filename) or "scan.pdf"
            path = None
            try:
                if os.path.splitext(original)[1].lower() != ".pdf":
                    raise ValueError(
                        f'"{original}" is not a PDF. Only PDF scan files are supported here.'
                    )

                file_storage.seek(0, os.SEEK_END)
                size = file_storage.tell()
                file_storage.seek(0)
                if size <= 0:
                    raise ValueError(f'"{original}" is empty.')
                if size > SCAN_PDF_MAX_BYTES:
                    raise ValueError(
                        f'"{original}" is {size / (1024 * 1024):.1f} MB — max 40 MB per scan PDF. '
                        "Upload one smaller file at a time, or use text-based Full Scan PDFs."
                    )

                os.makedirs(upload_dir, exist_ok=True)
                stored = f"{uuid.uuid4().hex}.pdf"
                path = os.path.join(upload_dir, stored)
                file_storage.save(path)
                ds._validate_pdf_file(path, original)

                max_pages, max_chars, allow_vision = 30, 50000, True
                if size > 8 * 1024 * 1024:
                    max_pages, max_chars, allow_vision = 20, 40000, False
                if size > 20 * 1024 * 1024:
                    max_pages, max_chars = 12, 30000

                text = ds.extract_text(
                    path,
                    original,
                    max_pages=max_pages,
                    max_chars=max_chars,
                    allow_grok_vision=allow_vision,
                )
                if ds.is_generated_report_export(text):
                    from report_generator import _parse_lines
                    if len(_parse_lines(text)) < 15:
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                        path = None
                        raise ValueError(
                            f'"{original}" looks like a portal download from this website — '
                            "upload the original scanner PDFs instead."
                        )
                if size < 4096 and not ds.scan_text_has_content(text):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    path = None
                    raise ValueError(
                        f'"{original}" is only {size:,} bytes with no scan data.'
                    )

                extraction_ok = not ds._pdf_extraction_failed(text)
                results.append(
                    {
                        "stored_filename": stored,
                        "original_name": original,
                        "extracted_text": text,
                        "extraction_ok": extraction_ok,
                        "file_size": os.path.getsize(path) if path else size,
                    }
                )
                print(
                    f"[Root Cause] Scan PDF OK: {original} ({size:,} bytes, "
                    f"{len(text.strip()):,} chars, imaging={ds.is_imaging_scan_format(text)})"
                )
            except ValueError as exc:
                errors.append(str(exc))
                print(f"[Root Cause] Scan PDF rejected: {exc}")
            except Exception as exc:
                msg = (
                    f'Could not process "{original}": {type(exc).__name__}: {exc}. '
                    "Try one file at a time, or a smaller scanner export."
                )
                errors.append(msg)
                print(f"[Root Cause] Scan PDF failed: {msg}")
                traceback.print_exc()
                if path:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        if not results and errors:
            raise ValueError(" ".join(errors))
        return results, errors

    ds.process_scan_pdf_uploads = process_scan_pdf_uploads
    print("[Root Cause] Patched process_scan_pdf_uploads for large imaging PDFs")


_ensure_body_overview()

# Load last known-good full app.py
_URL = f"{_RAW}/{_GOOD_APP_COMMIT}/app.py"
_src = _fetch(_URL)
_path = os.path.join(_HERE, "_app_restored.py")
try:
    with open(_path, "w", encoding="utf-8") as _f:
        _f.write(_src)
except Exception:
    _path = "<app_restored>"

exec(compile(_src, _path, "exec"), globals())

# Patch scan uploads after document_service is importable
try:
    _patch_scan_pdf_uploads()
except Exception as _patch_err:
    print(f"[Root Cause] Scan PDF patch failed: {_patch_err}")

# Apply Health Age + PDF live upgrades
try:
    from report_live_upgrades import apply_report_upgrades
    apply_report_upgrades(app, db, Report, reports_dir)
except Exception as _upgrade_err:
    print(f"[Root Cause] Live upgrades not applied: {_upgrade_err}")
    import traceback
    traceback.print_exc()
