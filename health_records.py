"""Categorized client record uploads for Grok wellness analysis.

Files accompany an existing hair + saliva scan. No portal passwords.
"""
from __future__ import annotations

import os
import sys
import uuid

from werkzeug.utils import secure_filename


CATEGORIES = {
    "wearable": {
        "label": "Wearable exports",
        "hint": "Apple Health, Fitbit, Garmin (ZIP, XML, CSV, JSON)",
        "accept": ".zip,.xml,.csv,.json,.txt",
        "exts": {".zip", ".xml", ".csv", ".json", ".txt"},
        "max_bytes": 200 * 1024 * 1024,
        "max_label": "200 MB",
        "grok_label": "Wearable export (Apple Health / Fitbit / Garmin)",
        "light_extract": True,
    },
    "labs": {
        "label": "Lab PDFs / blood work",
        "hint": "Lab results you already downloaded as PDF or text",
        "accept": ".pdf,.txt",
        "exts": {".pdf", ".txt"},
        "max_bytes": 25 * 1024 * 1024,
        "max_label": "25 MB",
        "grok_label": "Lab PDF / blood work",
        "light_extract": False,
    },
    "clinical": {
        "label": "Clinical visit summaries",
        "hint": "After-visit summaries already downloaded by you",
        "accept": ".pdf,.txt,.doc,.docx,.png,.jpg,.jpeg,.webp",
        "exts": {".pdf", ".txt", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp"},
        "max_bytes": 25 * 1024 * 1024,
        "max_label": "25 MB",
        "grok_label": "Clinical visit / after-visit summary",
        "light_extract": False,
    },
    "imaging": {
        "label": "Imaging report PDFs",
        "hint": "Radiology or imaging reports as PDF (not raw DICOM)",
        "accept": ".pdf",
        "exts": {".pdf"},
        "max_bytes": 40 * 1024 * 1024,
        "max_label": "40 MB",
        "grok_label": "Imaging report PDF",
        "light_extract": False,
    },
    "meds": {
        "label": "Medication / supplement lists",
        "hint": "Medication or supplement lists (PDF, text, photo, CSV)",
        "accept": ".pdf,.txt,.csv,.doc,.docx,.png,.jpg,.jpeg,.webp",
        "exts": {".pdf", ".txt", ".csv", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp"},
        "max_bytes": 15 * 1024 * 1024,
        "max_label": "15 MB",
        "grok_label": "Medication / supplement list",
        "light_extract": False,
    },
}

BLOCKED_EXTS = {
    ".exe", ".html", ".htm", ".js", ".php", ".sh", ".bat", ".cmd",
    ".dmg", ".app", ".msi", ".apk", ".iso", ".dll", ".com", ".scr",
}
MAX_FILES = 25


def category_meta(key):
    return CATEGORIES.get((key or "").strip().lower())


def _helpers():
    mod = sys.modules.get("__main__") or sys.modules.get("app")
    helpers = vars(mod) if mod else {}
    if "_get_current_user" not in helpers:
        import inspect
        for fr in inspect.stack():
            if "_get_current_user" in fr.frame.f_globals:
                helpers = fr.frame.f_globals
                break
    return helpers


def _validate_one(file_storage, category_key):
    meta = category_meta(category_key)
    if not meta:
        raise ValueError("Choose a record category.")
    if not file_storage or not file_storage.filename:
        raise ValueError("No file selected.")
    original = secure_filename(file_storage.filename) or "upload"
    ext = os.path.splitext(original)[1].lower()
    if ext in BLOCKED_EXTS:
        raise ValueError(f'"{original}" type is not allowed.')
    if ext not in meta["exts"]:
        raise ValueError(
            f'"{original}" is not accepted for {meta["label"]}. '
            f'Use {meta["accept"]}.'
        )
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size <= 0:
        raise ValueError(f'"{original}" is empty.')
    if size > meta["max_bytes"]:
        mb = size / (1024 * 1024)
        raise ValueError(
            f'"{original}" is {mb:.1f} MB — max {meta["max_label"]} for {meta["label"]}.'
        )
    return original, ext, size


def save_categorized_uploads(file_list, category_key, upload_dir):
    meta = category_meta(category_key)
    if not meta:
        raise ValueError("Choose a record category.")
    valid = [f for f in (file_list or []) if f and f.filename]
    if not valid:
        raise ValueError("Select at least one file.")
    if len(valid) > MAX_FILES:
        raise ValueError(f"Maximum {MAX_FILES} files per upload.")
    os.makedirs(upload_dir, exist_ok=True)
    saved, errors = [], []
    for fs in valid:
        try:
            original, ext, size = _validate_one(fs, category_key)
            stored = f"{uuid.uuid4().hex}{ext}"
            path = os.path.join(upload_dir, stored)
            fs.save(path)
            saved.append(
                {
                    "stored": stored,
                    "original": original,
                    "size": size,
                    "path": path,
                    "category": category_key,
                }
            )
        except ValueError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f'Could not save "{getattr(fs, "filename", "file")}": {exc}')
    if not saved and errors:
        raise ValueError(" ".join(errors))
    return saved, errors


def persist_client_records(helpers, email, saved_files, category_key, form_date=""):
    ClientDocument = helpers["ClientDocument"]
    db = helpers["db"]
    central_now = helpers["central_now"]
    documents_dir = helpers["documents_dir"]
    extract_text = helpers.get("extract_text")
    meta = category_meta(category_key) or CATEGORIES["wearable"]
    upload_dt = central_now()
    date = (form_date or "").strip() or upload_dt.strftime("%Y-%m-%d")
    created = []
    for item in saved_files:
        text = f"[{meta['grok_label']} uploaded: {item['original']}. File saved for wellness analysis.]"
        if not meta.get("light_extract") and extract_text:
            try:
                path = item.get("path") or os.path.join(documents_dir, item["stored"])
                extracted = extract_text(path, item["original"]) or ""
                if extracted.strip() and not extracted.startswith("[PDF uploaded:"):
                    text = extracted[:200000]
            except Exception as exc:
                print(f"[Root Cause] Record extract skipped for {item['original']}: {exc}")
        doc = ClientDocument(
            user_email=email,
            stored_filename=item["stored"],
            original_name=item["original"],
            extracted_text=text,
            test_date=date,
            grok_label=meta["grok_label"],
            uploaded_at=upload_dt.strftime("%Y-%m-%d %H:%M"),
        )
        db.session.add(doc)
        created.append(
            {
                "name": item["original"],
                "category": category_key,
                "category_label": meta["label"],
                "size": item["size"],
                "ok": True,
            }
        )
    db.session.commit()
    return created


def register_health_record_routes(app, db=None):
    """Override /health-app, add /export-records + multi-file API, wrap dashboard POST."""
    from flask import (
        flash,
        jsonify,
        redirect,
        render_template,
        request,
        session,
        url_for,
    )
    from werkzeug.security import check_password_hash

    helpers = _helpers()
    if db is not None:
        helpers["db"] = db
    helpers.setdefault("check_password_hash", check_password_hash)
    try:
        from document_service import extract_text as _extract_text
        helpers.setdefault("extract_text", _extract_text)
    except Exception:
        pass

    def _user():
        fn = helpers.get("_get_current_user")
        if fn:
            try:
                return fn()
            except Exception:
                return None
        if session.get("user_id"):
            User = helpers.get("User")
            if User:
                try:
                    return User.query.get(session["user_id"])
                except Exception:
                    return None
        return None

    def health_app():
        return render_template(
            "health_app.html",
            categories=CATEGORIES,
            logged_in=bool(_user() or session.get("user_id")),
        )

    def export_records():
        return render_template("export_records.html")

    def api_upload_records():
        user = _user()
        if not user:
            return jsonify(
                {"error": "Please log in to upload records.", "login": True}
            ), 401
        if request.form.get("portal_password") or request.form.get("mychart_password"):
            return jsonify(
                {
                    "error": "Do not send portal passwords. Download the file yourself, then upload it here."
                }
            ), 400
        category = (request.form.get("category") or "").strip().lower()
        if not category_meta(category):
            return jsonify({"error": "Choose a valid record category."}), 400
        files = request.files.getlist("files") or request.files.getlist("file")
        documents_dir = helpers.get("documents_dir")
        if not documents_dir:
            return jsonify({"error": "Upload storage is not ready."}), 503
        try:
            saved, partial = save_categorized_uploads(files, category, documents_dir)
            created = persist_client_records(
                helpers,
                user.email,
                saved,
                category,
                form_date=request.form.get("test_date") or "",
            )
            return jsonify(
                {
                    "success": True,
                    "message": (
                        f"Saved {len(created)} file(s) for wellness analysis. "
                        "Open your dashboard and choose Request Updated Grok Analysis "
                        "when you want them included with your scan."
                    ),
                    "files": created,
                    "errors": partial,
                }
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            print(f"[Root Cause] upload_records failed: {exc}")
            return jsonify({"error": "Upload failed. Try one smaller file."}), 400

    def api_upload_health():
        """Back-compat for the PWA + desktop tool; now multi-file + category."""
        user = _user()
        if not user:
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            User = helpers.get("User")
            check_pw = helpers.get("check_password_hash")
            if User and check_pw and email and password:
                user = User.query.filter(
                    helpers["db"].func.lower(User.email) == email
                ).first()
                if not user or not check_pw(user.password, password):
                    return jsonify({"error": "Invalid email or password"}), 401
            else:
                return jsonify({"error": "Please log in to upload records."}), 401
        if request.form.get("portal_password"):
            return jsonify(
                {"error": "Do not send portal passwords. Export the file yourself."}
            ), 400
        category = (request.form.get("category") or request.form.get("document_type") or "wearable")
        if category not in CATEGORIES:
            category = "wearable"
        files = request.files.getlist("files") or request.files.getlist("file")
        files = [f for f in files if f and f.filename]
        json_data = request.get_json(silent=True) or {}
        documents_dir = helpers.get("documents_dir")
        ClientDocument = helpers.get("ClientDocument")
        central_now = helpers.get("central_now")
        if json_data.get("health_data") and not files and ClientDocument:
            import json
            summary = json.dumps(json_data["health_data"])[:8000]
            upload_dt = central_now()
            doc = ClientDocument(
                user_email=user.email,
                stored_filename="",
                original_name="HealthKit Data (iOS App)",
                extracted_text=f"[Wearable data from iOS app]\n{summary}",
                test_date=upload_dt.strftime("%Y-%m-%d"),
                grok_label=CATEGORIES["wearable"]["grok_label"],
                uploaded_at=upload_dt.strftime("%Y-%m-%d %H:%M"),
            )
            helpers["db"].session.add(doc)
            helpers["db"].session.commit()
            return jsonify(
                {
                    "success": True,
                    "message": "Wearable data saved. Request an analysis update from your dashboard.",
                }
            )
        if not files:
            return jsonify({"error": "No file provided"}), 400
        try:
            saved, partial = save_categorized_uploads(files, category, documents_dir)
            created = persist_client_records(
                helpers,
                user.email,
                saved,
                category,
                form_date=request.form.get("test_date") or "",
            )
            return jsonify(
                {
                    "success": True,
                    "message": (
                        f"Uploaded {len(created)} file(s). "
                        "Go to your dashboard and request an analysis update so Grok "
                        "can incorporate the new data with your scan."
                    ),
                    "files": created,
                    "errors": partial,
                }
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            print(f"[Root Cause] upload_health failed: {exc}")
            return jsonify({"error": "Upload failed: " + str(exc)}), 400

    orig_dashboard = app.view_functions.get("dashboard")

    def dashboard_wrapped():
        if request.method == "POST" and request.form.get("action") == "upload_records":
            user = _user()
            if not user:
                return redirect(url_for("login"))
            category = (request.form.get("category") or "").strip().lower()
            files = request.files.getlist("files") or request.files.getlist("documents")
            try:
                saved, partial = save_categorized_uploads(
                    files, category, helpers["documents_dir"]
                )
                created = persist_client_records(
                    helpers,
                    user.email,
                    saved,
                    category,
                    form_date=request.form.get("test_date") or "",
                )
                msg = f'Uploaded {len(created)} file(s) ({category_meta(category)["label"]}).'
                msg += " Click Request Updated Grok Analysis when you want them included."
                if partial:
                    msg += " Some files skipped: " + "; ".join(partial[:3])
                flash(msg, "success")
            except Exception as exc:
                flash(f"Upload failed: {exc}", "error")
            render = helpers.get("_render_client_dashboard")
            if render:
                return render(user.email)
            return redirect(url_for("dashboard"))
        if orig_dashboard:
            return orig_dashboard()
        return redirect(url_for("login"))

    app.view_functions["health_app"] = health_app
    app.view_functions["api_client_upload_health"] = api_upload_health
    if "dashboard" in app.view_functions:
        app.view_functions["dashboard"] = dashboard_wrapped

    existing = {rule.endpoint for rule in app.url_map.iter_rules()}
    if "export_records" not in existing:
        app.add_url_rule("/export-records", "export_records", export_records)
    else:
        app.view_functions["export_records"] = export_records
    if "api_client_upload_records" not in existing:
        app.add_url_rule(
            "/api/client/upload_records",
            "api_client_upload_records",
            api_upload_records,
            methods=["POST"],
        )
    else:
        app.view_functions["api_client_upload_records"] = api_upload_records

    print("[Root Cause] Health record categories + /export-records registered")
