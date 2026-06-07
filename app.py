from flask import (
    Flask, render_template, request, redirect, url_for, flash, session,
    send_from_directory, abort,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from datetime import datetime
from collections import OrderedDict

from report_generator import generate_report_html, generate_report_text
from pdf_service import save_report_pdf, pdf_to_bytes

from document_service import (
    save_upload, save_multiple_uploads, extract_text, combined_document_text,
    process_scan_pdf_uploads, merge_scan_sources, scan_pdf_extraction_issues,
    parse_date_from_text, scan_text_has_content, report_html_has_findings,
    build_pdf_results_from_paths, describe_pdf_uploads,
)
from client_portal import get_personalized_recommendations
from health_advisor import get_health_recommendations, classify_medical_document, get_last_grok_error
from scan_reconciliation import reconcile_scan_with_blood_tests
from notification_service import (
    notify_client_analysis_update, notify_admin_analysis_request,
    deliver_report_to_client,
)
from stripe_service import create_checkout_session, stripe_configured
from persistent_storage import setup_persistent_paths

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'rootcause2026secretkey')
app.config['MAX_CONTENT_LENGTH'] = 80 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Use RENDER (auto-set on Render.com), not SITE_URL — SITE_URL=https breaks local HTTP sessions.
_on_render = bool(os.environ.get('RENDER'))
_cookie_secure_env = os.environ.get('SESSION_COOKIE_SECURE', '').lower()
if _cookie_secure_env == 'true':
    app.config['SESSION_COOKIE_SECURE'] = True
elif _cookie_secure_env == 'false':
    app.config['SESSION_COOKIE_SECURE'] = False
else:
    app.config['SESSION_COOKIE_SECURE'] = _on_render
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 14
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

basedir = os.path.abspath(os.path.dirname(__file__))
_storage = setup_persistent_paths(basedir)
data_dir = _storage['data_dir']
instance_dir = _storage['instance_dir']
uploads_dir = _storage['uploads_dir']
reports_dir = _storage['reports_dir']
documents_dir = _storage['documents_dir']
scan_pdfs_dir = _storage['scan_pdfs_dir']

if os.environ.get('RENDER'):
    print(f'[Root Cause] Persistent data directory: {data_dir}')

app.config['SQLALCHEMY_DATABASE_URI'] = _storage['database_uri']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200))
    raw_data = db.Column(db.Text)
    generated_report = db.Column(db.Text)
    plain_text = db.Column(db.Text)
    ai_recommendations = db.Column(db.Text)
    pdf_filename = db.Column(db.String(200))
    email_sent = db.Column(db.Boolean, default=False)
    sms_sent = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    approved_at = db.Column(db.String(50))
    date = db.Column(db.String(50))
    analysis_updated = db.Column(db.String(50))
    original_generated_report = db.Column(db.Text)
    original_ai_recommendations = db.Column(db.Text)
    blood_reconciliation_html = db.Column(db.Text)
    reconciled_at = db.Column(db.String(50))


class ClientDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    stored_filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200))
    extracted_text = db.Column(db.Text)
    test_date = db.Column(db.String(20))
    grok_label = db.Column(db.String(200))
    grok_date = db.Column(db.String(20))
    uploaded_at = db.Column(db.String(50))


class ReportScanPdf(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=False)
    stored_filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200))
    extracted_text = db.Column(db.Text)
    uploaded_at = db.Column(db.String(50))

    report = db.relationship('Report', backref=db.backref('scan_pdfs', lazy=True))


def ensure_admin_user():
    admin_email = 'michaelpeatross@gmail.com'
    bootstrap_pw = os.environ.get('ADMIN_PASSWORD', 'admin123')
    user = User.query.filter(db.func.lower(User.email) == admin_email).first()
    if not user:
        user = User(
            name='Michael Peatross',
            email=admin_email,
            password=generate_password_hash(bootstrap_pw),
            is_admin=True,
        )
        db.session.add(user)
    else:
        user.is_admin = True
        if not user.name:
            user.name = 'Michael Peatross'
        if not check_password_hash(user.password, bootstrap_pw):
            user.password = generate_password_hash(bootstrap_pw)
    db.session.commit()


def migrate_schema():
    """Upgrade schema from older deployments."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    if 'user' in tables:
        user_cols = {c['name'] for c in inspector.get_columns('user')}
        for col, col_type in {'is_admin': 'BOOLEAN DEFAULT 0', 'phone': 'VARCHAR(20)'}.items():
            if col not in user_cols:
                with db.engine.connect() as conn:
                    conn.execute(text(f'ALTER TABLE user ADD COLUMN {col} {col_type}'))
                    conn.commit()

    report_required = {'user_email', 'title', 'raw_data', 'generated_report', 'date'}
    if 'report' in tables:
        report_cols = {c['name'] for c in inspector.get_columns('report')}
        if not report_required.issubset(report_cols):
            with db.engine.connect() as conn:
                conn.execute(text('DROP TABLE report'))
                conn.commit()
            db.create_all()
        else:
            new_cols = {
                'plain_text': 'TEXT',
                'ai_recommendations': 'TEXT',
                'pdf_filename': 'VARCHAR(200)',
                'email_sent': 'BOOLEAN DEFAULT 0',
                'sms_sent': 'BOOLEAN DEFAULT 0',
                'approved': 'BOOLEAN DEFAULT 0',
                'approved_at': 'VARCHAR(50)',
                'analysis_updated': 'VARCHAR(50)',
                'original_generated_report': 'TEXT',
                'original_ai_recommendations': 'TEXT',
                'blood_reconciliation_html': 'TEXT',
                'reconciled_at': 'VARCHAR(50)',
            }
            for col, col_type in new_cols.items():
                if col not in report_cols:
                    with db.engine.connect() as conn:
                        conn.execute(text(f'ALTER TABLE report ADD COLUMN {col} {col_type}'))
                        conn.commit()

    if 'client_document' in tables:
        doc_cols = {c['name'] for c in inspector.get_columns('client_document')}
        for col, col_type in {
            'test_date': 'VARCHAR(20)',
            'grok_label': 'VARCHAR(200)',
            'grok_date': 'VARCHAR(20)',
        }.items():
            if col not in doc_cols:
                with db.engine.connect() as conn:
                    conn.execute(text(f'ALTER TABLE client_document ADD COLUMN {col} {col_type}'))
                    conn.commit()

    if 'client_document' not in tables or 'report_scan_pdf' not in tables:
        db.create_all()


def _normalize_email(email):
    return (email or '').strip().lower()


def _normalize_stored_emails():
    """Keep user emails lowercase so login always matches registration."""
    from sqlalchemy import inspect
    if 'user' not in inspect(db.engine).get_table_names():
        return
    seen = set()
    for user in User.query.order_by(User.id).all():
        normalized = _normalize_email(user.email)
        if not normalized:
            continue
        if normalized in seen:
            continue
        if user.email != normalized:
            conflict = User.query.filter(
                db.func.lower(User.email) == normalized,
                User.id != user.id,
            ).first()
            if not conflict:
                user.email = normalized
        seen.add(normalized)
    db.session.commit()


def _backfill_empty_original_ai():
    """Repair reports published before scan-only Grok analysis existed."""
    from health_advisor import _local_original_scan_analysis_html
    updated = False
    for report in Report.query.all():
        if (report.original_ai_recommendations or '').strip():
            continue
        raw = report.raw_data or ''
        if not scan_text_has_content(raw):
            continue
        client_name = _client_display_name(report.user_email)
        ai = _local_original_scan_analysis_html(raw, client_name)
        report.original_ai_recommendations = ai
        if not (report.ai_recommendations or '').strip():
            report.ai_recommendations = ai
        updated = True
    if updated:
        db.session.commit()


def _user_owns_report(report):
    if session.get('is_admin'):
        return True
    return _normalize_email(session.get('email')) == _normalize_email(report.user_email)


def _get_client_documents(email):
    return ClientDocument.query.filter(
        db.func.lower(ClientDocument.user_email) == _normalize_email(email)
    ).order_by(ClientDocument.id.desc()).all()


def _apply_document_classification(doc):
    """Store Grok-inferred document name and test date on a ClientDocument."""
    meta = classify_medical_document(doc.extracted_text, doc.original_name)
    doc.grok_label = (meta.get('document_name') or 'Medical document')[:200]
    doc.grok_date = meta.get('test_date')


def _save_client_documents(email, saved_files, form_date='', upload_dt=None):
    """Persist uploaded medical documents for a client portal."""
    upload_dt = upload_dt or datetime.now()
    count = 0
    for stored, original in saved_files:
        path = os.path.join(documents_dir, stored)
        text = extract_text(path, original)
        parsed = parse_date_from_text(text)
        if form_date:
            test_date = form_date
        elif parsed:
            test_date = parsed.strftime('%Y-%m-%d')
        else:
            test_date = upload_dt.strftime('%Y-%m-%d')

        doc = ClientDocument(
            user_email=email,
            stored_filename=stored,
            original_name=original,
            extracted_text=text,
            test_date=test_date,
            uploaded_at=upload_dt.strftime('%Y-%m-%d %H:%M'),
        )
        _apply_document_classification(doc)
        db.session.add(doc)
        count += 1
    return count


def _ensure_document_labels(documents):
    """Backfill Grok labels for documents uploaded before classification existed."""
    updated = False
    for doc in documents:
        if doc.grok_label:
            continue
        _apply_document_classification(doc)
        updated = True
    if updated:
        db.session.commit()


def _client_display_name(email):
    user = User.query.filter(db.func.lower(User.email) == _normalize_email(email)).first()
    if user and user.name:
        return user.name
    return email.split('@')[0]


def _attach_scan_pdfs_to_report(report, pdf_results):
    """Link uploaded scan PDFs to a report record."""
    for pdf in pdf_results:
        entry = ReportScanPdf(
            report_id=report.id,
            stored_filename=pdf['stored_filename'],
            original_name=pdf['original_name'],
            extracted_text=pdf['extracted_text'],
            uploaded_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        )
        db.session.add(entry)


def _medical_context(email):
    docs = _get_client_documents(email)
    return combined_document_text(docs, recent_only=False), len(docs)


def _prefer_full_scan_template(title, raw_data, pdf_results=None):
    """Use the Full Scan PDF layout when original scanner PDF content is detected."""
    from document_service import is_generated_report_export, is_imaging_scan_format
    from scan_template import uses_template_format
    if is_generated_report_export(raw_data or '') or is_imaging_scan_format(raw_data or ''):
        return False
    return uses_template_format(raw_data or '', title=title)


def _build_scan_report_html(email, title, raw_data, pdf_results=None):
    """Build formatted scan HTML (fast — no Grok API call)."""
    client_name = _client_display_name(email)
    prefer_template = _prefer_full_scan_template(title, raw_data, pdf_results)
    scan_html = generate_report_html(
        email, title, raw_data, ai_recommendations_html=None,
        client_name=client_name, prefer_template=prefer_template,
    )
    return scan_html, prefer_template, client_name


def _run_original_scan_grok(raw_data, client_name, email, prefer_template):
    """Call Grok for original scan analysis; falls back to local summary."""
    from health_advisor import _local_original_scan_analysis_html

    local_ai = _local_original_scan_analysis_html(raw_data, client_name)
    original_ai, ai_source = get_health_recommendations(
        raw_data, '', client_name, email, full_scan_mode=prefer_template,
    )
    if not (original_ai or '').strip():
        return local_ai, 'local', get_last_grok_error()
    grok_error = get_last_grok_error() if ai_source != 'grok' else None
    return original_ai, ai_source, grok_error


def _refresh_original_grok_analysis(report):
    """Re-run Grok using bio scan data only; updates original_ai_recommendations."""
    scan_raw = _resolve_report_scan_data(report)
    if not scan_text_has_content(scan_raw):
        return report, 'No usable scan data on this report.'

    if scan_raw != (report.raw_data or ''):
        report.raw_data = scan_raw

    client_name = _client_display_name(report.user_email)
    prefer_template = _prefer_full_scan_template(report.title, scan_raw)
    original_ai, ai_source, grok_error = _run_original_scan_grok(
        scan_raw, client_name, report.user_email, prefer_template,
    )

    report.original_ai_recommendations = original_ai
    if not report.analysis_updated:
        report.ai_recommendations = original_ai

    if ai_source == 'grok':
        return report, 'Grok original scan analysis updated.'
    return report, f'Local summary used{f" ({grok_error})" if grok_error else ""}.'


def _regenerate_report_analysis(report, notify_client=False, notify_admin=False):
    """Re-run Grok analysis using scan data + all uploaded medical documents."""
    email = report.user_email
    medical_text, doc_count = _medical_context(email)
    client_name = _client_display_name(email)
    user = User.query.filter(db.func.lower(User.email) == _normalize_email(email)).first()

    scan_raw = _resolve_report_scan_data(report)
    if scan_raw != (report.raw_data or ''):
        report.raw_data = scan_raw

    _snapshot_original_report(report)
    prefer_template = _prefer_full_scan_template(report.title, scan_raw)

    recon_result = reconcile_scan_with_blood_tests(
        scan_raw, medical_text, client_name, email,
    ) if medical_text and len(medical_text.strip()) >= 80 else None

    if recon_result:
        ai_html = recon_result['updated_ai_html']
        blood_html = recon_result['reconciliation_html']
        report.blood_reconciliation_html = blood_html
        report.reconciled_at = datetime.now().strftime('%Y-%m-%d %H:%M')
    else:
        ai_html, _ = get_health_recommendations(
            scan_raw, medical_text, client_name, email,
            full_scan_mode=prefer_template,
        )
        blood_html = None

    report.ai_recommendations = ai_html
    report.plain_text = generate_report_text(
        email, report.title, scan_raw, ai_html
    )
    report.analysis_updated = datetime.now().strftime('%Y-%m-%d %H:%M')
    pdf_html = generate_report_html(
        email, report.title, scan_raw, ai_html, client_name=client_name,
        prefer_template=prefer_template,
        blood_reconciliation_html=blood_html,
    )
    _save_pdf_for_report(report, pdf_html)

    messages = []
    if notify_client:
        pdf_bytes = pdf_to_bytes(report.generated_report)
        e_ok, e_msg, s_ok, s_msg = notify_client_analysis_update(
            email,
            client_name,
            user.phone if user else '',
            report.title,
            report.plain_text,
            pdf_bytes,
        )
        report.email_sent = e_ok
        messages.extend([e_msg, s_msg])
    if notify_admin:
        a_e_ok, a_e_msg, a_s_ok, a_s_msg = notify_admin_analysis_request(
            client_name, email, report.title
        )
        messages.extend([a_e_msg, a_s_msg])

    return report, doc_count, messages


def _group_reports_by_date(reports):
    """Organize reports into date groups for client scan history."""
    groups = OrderedDict()
    for report in reports:
        date_key = (report.date or 'Unknown')[:10]
        try:
            dt = datetime.strptime(date_key, '%Y-%m-%d')
            label = dt.strftime('%B %d, %Y')
        except ValueError:
            label = date_key
        groups.setdefault(label, []).append(report)
    return groups


def _parse_report_datetime(date_str):
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str[:16] if ' ' in date_str else date_str[:10], fmt)
        except ValueError:
            continue
    return None


def _last_scan_bucket(days):
    """Map days since last scan to admin follow-up bucket."""
    if days <= 1:
        return '1_day'
    if days <= 7:
        return '1_week'
    if days <= 30:
        return '1_month'
    if days <= 60:
        return '2_months'
    if days <= 90:
        return '3_months'
    if days < 180:
        return '5_months'
    return '6_months_plus'


def _non_admin_users():
    """All client accounts (treat NULL is_admin as non-admin)."""
    return User.query.filter(User.is_admin.isnot(True)).order_by(User.id.desc()).all()


def _get_clients_for_admin():
    """All clients available for report assignment (accounts, uploads, past reports)."""
    clients = {}

    for user in _non_admin_users():
        email = _normalize_email(user.email)
        clients[email] = {
            'email': email,
            'name': user.name or email.split('@')[0],
            'has_account': True,
            'user_id': user.id,
        }

    for doc in ClientDocument.query.all():
        email = _normalize_email(doc.user_email)
        if email and email not in clients:
            clients[email] = {
                'email': email,
                'name': email.split('@')[0],
                'has_account': False,
                'user_id': 0,
            }

    for report in Report.query.all():
        email = _normalize_email(report.user_email)
        if email and email not in clients:
            clients[email] = {
                'email': email,
                'name': email.split('@')[0],
                'has_account': False,
                'user_id': 0,
            }

    result = []
    for email, info in clients.items():
        docs = ClientDocument.query.filter(
            db.func.lower(ClientDocument.user_email) == email
        ).order_by(ClientDocument.id.desc()).all()
        doc_count = len(docs)
        report_count = Report.query.filter(
            db.func.lower(Report.user_email) == email
        ).count()
        latest_upload = docs[0].uploaded_at if docs else None
        result.append({
            **info,
            'doc_count': doc_count,
            'report_count': report_count,
            'latest_upload': latest_upload,
            'awaiting_scan': report_count == 0,
        })

    result.sort(key=lambda c: (
        0 if (c['doc_count'] > 0 and c['awaiting_scan']) else 1,
        0 if c['awaiting_scan'] else 1,
        -(c['user_id'] or 0),
        c['name'].lower(),
    ))
    return result


def _split_clients_for_admin(clients):
    """Group clients for the admin picker and awaiting-scan panel."""
    awaiting_with_docs = [
        c for c in clients if c['awaiting_scan'] and c['doc_count'] > 0
    ]
    awaiting_accounts = [
        c for c in clients if c['awaiting_scan'] and c['doc_count'] == 0
    ]
    with_reports = [c for c in clients if not c['awaiting_scan']]
    return {
        'awaiting_with_docs': awaiting_with_docs,
        'awaiting_accounts': awaiting_accounts,
        'with_reports': with_reports,
    }


def _resolve_client_email_from_form():
    """Read selected client or new-email field from the admin report form."""
    pick = (request.form.get('client_email') or '').strip()
    if pick == '__new__':
        return _normalize_email(request.form.get('new_email', ''))
    if pick:
        return _normalize_email(pick)
    return _normalize_email(request.form.get('email', ''))


def _group_clients_by_last_scan():
    """Group clients by how long ago their most recent scan was."""
    bucket_defs = [
        ('1_day', 'Within 1 day'),
        ('1_week', '1 day – 1 week'),
        ('1_month', '1 week – 1 month'),
        ('2_months', '1 – 2 months'),
        ('3_months', '2 – 3 months'),
        ('5_months', '3 – 5 months'),
        ('6_months_plus', '6 months & older'),
    ]
    buckets = {key: {'key': key, 'label': label, 'clients': []} for key, label in bucket_defs}

    reports = Report.query.order_by(Report.id.desc()).all()
    latest_by_email = {}
    for report in reports:
        email = _normalize_email(report.user_email)
        report_dt = _parse_report_datetime(report.date)
        existing = latest_by_email.get(email)
        if not existing:
            latest_by_email[email] = (report, report_dt)
            continue
        existing_dt = existing[1]
        if report_dt and (not existing_dt or report_dt > existing_dt):
            latest_by_email[email] = (report, report_dt)

    users = {
        _normalize_email(u.email): u
        for u in _non_admin_users()
    }
    now = datetime.now()

    for email, (report, report_dt) in latest_by_email.items():
        if not report_dt:
            continue
        days = (now - report_dt).total_seconds() / 86400
        bucket_key = _last_scan_bucket(days)
        user = users.get(email)
        name = (user.name if user and user.name else email.split('@')[0])
        days_display = max(0, int(days))
        if days_display == 0:
            days_label = 'today'
        elif days_display == 1:
            days_label = '1 day ago'
        else:
            days_label = f'{days_display} days ago'

        buckets[bucket_key]['clients'].append({
            'email': email,
            'name': name,
            'last_scan_date': report.date,
            'last_scan_title': report.title,
            'days_ago': days_display,
            'days_label': days_label,
            'approved': bool(report.approved),
        })

    for bucket in buckets.values():
        bucket['clients'].sort(key=lambda c: c['days_ago'])

    return [buckets[key] for key, _label in bucket_defs]


def _process_admin_scan_input(pasted_text):
    """Handle pasted text plus any uploaded scan PDFs from the admin form."""
    file_list = request.files.getlist('scan_pdfs')
    if not any(f and f.filename for f in file_list):
        print('[Root Cause] Admin scan upload: no PDF files in form data')
    pdf_results, pdf_errors = process_scan_pdf_uploads(file_list, scan_pdfs_dir)
    return merge_scan_sources(pasted_text, pdf_results), pdf_results, pdf_errors


def _resolve_report_scan_data(report):
    """Rebuild scan text from stored raw_data and admin-linked scan PDFs."""
    raw = report.raw_data or ''
    if scan_text_has_content(raw):
        return raw

    pdf_results = build_pdf_results_from_paths(report.scan_pdfs, scan_pdfs_dir)
    if pdf_results:
        return merge_scan_sources('', pdf_results)
    return raw


def _report_has_scan_data(report):
    """True when a report has parseable scan content (paste or linked PDFs)."""
    return bool(report and scan_text_has_content(_resolve_report_scan_data(report)))


def _report_has_substantive_html(report):
    """True when the formatted report HTML includes real scan findings."""
    return bool(
        report
        and report.generated_report
        and report_html_has_findings(report.generated_report)
    )


def _unpublish_empty_reports():
    """Hide approved reports that only contain an empty cover-page shell."""
    updated = False
    for report in Report.query.filter(Report.approved == True).all():
        if report.generated_report and not report_html_has_findings(report.generated_report):
            report.approved = False
            report.approved_at = None
            updated = True
    if updated:
        db.session.commit()


def _scan_input_error_message(combined_raw, pdf_results):
    """User-facing message when scan text cannot be parsed."""
    for issue in scan_pdf_extraction_issues(pdf_results):
        return issue
    from document_service import is_generated_report_export
    if is_generated_report_export(combined_raw or ''):
        return (
            'This PDF was downloaded from this website (cover page / summary only) — '
            'it is not the original bio scan. Upload the Full Scan PDF from your '
            'bioenergetic scanner software (with Energetic System Performance, '
            'Sensitivities, Toxins, Metabolic Results) or paste the raw scan text below.'
        )
    if not (combined_raw or '').strip():
        return 'Paste raw scan data or upload at least one scan PDF.'
    return (
        'Could not read usable scan data from the upload. '
        'Paste the scan text or upload the original Full Scan PDF from your scanner software.'
    )


def _create_published_scan_report(email, title, combined_raw, pdf_results=None):
    """
    Generate, publish, and persist a scan report for the client portal.
    Saves the scan report first, then calls Grok (avoids 502 if Grok is slow).
    Returns (report, error_message, ai_source, grok_error).
    """
    if not scan_text_has_content(combined_raw):
        return None, _scan_input_error_message(combined_raw, pdf_results), None, None

    scan_html, prefer_template, client_name = _build_scan_report_html(
        email, title, combined_raw, pdf_results=pdf_results,
    )
    if not report_html_has_findings(scan_html):
        return None, _scan_input_error_message(combined_raw, pdf_results), None, None

    from health_advisor import _local_original_scan_analysis_html
    local_ai = _local_original_scan_analysis_html(combined_raw, client_name)

    report = Report(
        user_email=email,
        title=title,
        raw_data=combined_raw,
        generated_report=scan_html,
        original_generated_report=scan_html,
        plain_text=generate_report_text(email, title, combined_raw, local_ai),
        original_ai_recommendations=local_ai,
        ai_recommendations=local_ai,
        date=datetime.now().strftime('%Y-%m-%d %H:%M'),
    )
    _publish_report_to_portal(report)
    db.session.add(report)
    db.session.flush()

    if pdf_results:
        _attach_scan_pdfs_to_report(report, pdf_results)
    db.session.commit()

    original_ai, ai_source, grok_error = _run_original_scan_grok(
        combined_raw, client_name, email, prefer_template,
    )
    if (original_ai or '').strip():
        report.original_ai_recommendations = original_ai
        report.ai_recommendations = original_ai
        report.plain_text = generate_report_text(email, title, combined_raw, original_ai)
        db.session.commit()

    try:
        _save_pdf_for_report(report, scan_html)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return report, None, ai_source, grok_error


def _save_pdf_for_report(report, html_report):
    pdf_name = f'report_{report.id}.pdf'
    pdf_path = os.path.join(reports_dir, pdf_name)
    if save_report_pdf(html_report, pdf_path):
        report.pdf_filename = pdf_name
        return True
    return False


def _snapshot_original_report(report):
    """Preserve the first published scan report and Grok analysis."""
    if report.generated_report and not report.original_generated_report:
        report.original_generated_report = report.generated_report
    if report.ai_recommendations and not report.original_ai_recommendations:
        report.original_ai_recommendations = report.ai_recommendations


def _publish_report_to_portal(report):
    """Make a generated report visible on the client's portal."""
    _snapshot_original_report(report)
    if not report.approved:
        report.approved = True
        report.approved_at = datetime.now().strftime('%Y-%m-%d %H:%M')


def _apply_blood_reconciliation(report):
    """
    Compare original scan with uploaded blood tests; update report and AI analysis.
    Returns (report, doc_count, messages) or (None, 0, [error]) if no labs uploaded.
    """
    email = report.user_email
    medical_text, doc_count = _medical_context(email)
    if not medical_text or len(medical_text.strip()) < 80:
        return report, doc_count, [
            'No blood test or lab documents found. Upload lab work first.',
        ]

    _snapshot_original_report(report)
    client_name = _client_display_name(email)
    scan_raw = _resolve_report_scan_data(report)
    if scan_raw != (report.raw_data or ''):
        report.raw_data = scan_raw
    result = reconcile_scan_with_blood_tests(
        scan_raw, medical_text, client_name, email,
    )
    if not result:
        return report, doc_count, ['Could not reconcile scan with blood tests.']

    prefer_template = _prefer_full_scan_template(report.title, scan_raw)
    report.blood_reconciliation_html = result['reconciliation_html']
    report.ai_recommendations = result['updated_ai_html']
    report.reconciled_at = datetime.now().strftime('%Y-%m-%d %H:%M')
    report.analysis_updated = report.reconciled_at
    report.plain_text = generate_report_text(
        email, report.title, scan_raw, result['updated_ai_html'],
    )
    pdf_html = generate_report_html(
        email,
        report.title,
        scan_raw,
        result['updated_ai_html'],
        client_name=client_name,
        prefer_template=prefer_template,
        blood_reconciliation_html=result['reconciliation_html'],
    )
    _save_pdf_for_report(report, pdf_html)
    source = result.get('source', 'grok')
    return report, doc_count, [
        f'Scan updated with blood test comparison ({doc_count} document(s), {source}).',
    ]


def _client_has_usable_scan_report(email):
    """Latest report with parseable scan content for this client."""
    report = Report.query.filter(
        db.func.lower(Report.user_email) == _normalize_email(email),
        Report.generated_report.isnot(None),
    ).order_by(Report.id.desc()).first()
    if not report:
        return None
    if scan_text_has_content(_resolve_report_scan_data(report)):
        return report
    return None


def _approve_and_send_report(report, send_email=False, send_sms=False):
    """Publish to client portal and optionally deliver via email/SMS."""
    user = User.query.filter(
        db.func.lower(User.email) == _normalize_email(report.user_email)
    ).first()
    client_name = _client_display_name(report.user_email)
    client_phone = user.phone if user else ''

    _publish_report_to_portal(report)

    pdf_bytes = None
    if report.generated_report and send_email:
        pdf_bytes = pdf_to_bytes(report.generated_report)

    results = deliver_report_to_client(
        report.user_email,
        client_name,
        client_phone,
        report.title,
        report.plain_text or '',
        pdf_bytes=pdf_bytes,
        send_email=send_email,
        send_sms=send_sms,
    )

    messages = []
    for channel, ok, msg in results:
        if channel == 'email':
            if send_email:
                report.email_sent = bool(ok)
                messages.append(msg)
        elif channel == 'sms':
            if send_sms:
                report.sms_sent = bool(ok)
                messages.append(msg)

    if not send_email and not send_sms:
        messages.append('Report is on the client portal (no email or text sent).')

    return messages


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/buy')
def buy():
    return render_template('buy.html', stripe_ready=stripe_configured())


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout():
    site_url = os.environ.get('SITE_URL', request.host_url.rstrip('/'))
    email = request.form.get('email', '').strip() or session.get('email') or None
    coupon = request.form.get('coupon', '').strip()
    product = request.form.get('product') or request.args.get('product', 'single')
    session_url, error = create_checkout_session(site_url, email, coupon, product)
    if session_url:
        return redirect(session_url)
    flash(error or 'Could not start checkout.', 'error')
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('buy'))


@app.route('/checkout/success')
def checkout_success():
    return render_template('checkout_success.html')


@app.route('/instructions')
def instructions():
    return render_template('instructions.html')


def _find_user_by_email(email):
    """Case-insensitive user lookup."""
    normalized = _normalize_email(email)
    if not normalized:
        return None
    return User.query.filter(db.func.lower(User.email) == normalized).first()


def _start_user_session(user):
    session.permanent = True
    session['user_id'] = user.id
    session['email'] = user.email
    session['name'] = user.name or user.email.split('@')[0]
    session['is_admin'] = bool(user.is_admin)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action', 'login')
        raw_email = request.form.get('email', '').strip()
        email = _normalize_email(raw_email)
        password = request.form.get('password', '')

        if action == 'reset_password':
            new_password = request.form.get('new_password', '')
            confirm = request.form.get('confirm_password', '')
            user = _find_user_by_email(email)
            if not user:
                flash('No account found for that email. Create a free account first.', 'error')
            elif len(new_password) < 6:
                flash('Password must be at least 6 characters.', 'error')
            elif new_password != confirm:
                flash('Passwords do not match.', 'error')
            else:
                user.password = generate_password_hash(new_password)
                db.session.commit()
                flash('Password updated. Please sign in with your new password.', 'success')
            return render_template('login.html', show_reset=True, email=raw_email)

        user = _find_user_by_email(email)
        if user and user.password and check_password_hash(user.password, password):
            _start_user_session(user)
            flash('Welcome back!', 'success')
            return redirect(url_for('admin') if user.is_admin else url_for('dashboard'))

        if not user:
            has_reports = Report.query.filter(
                db.func.lower(Report.user_email) == email
            ).first()
            if has_reports:
                flash(
                    'No login account yet, but we have reports for this email. '
                    'Click Create Account and use the same email to access your portal.',
                    'error',
                )
            else:
                flash('No account found. Create a free account or check your email.', 'error')
        elif not user.password:
            flash('Account needs a password. Use "Forgot password" below to set one.', 'error')
        else:
            flash(
                f'Incorrect password for {raw_email}. Use Forgot Password to reset it.',
                'error',
            )

    return render_template('login.html', email=request.args.get('email', ''))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        raw_email = request.form.get('email', '').strip()
        email = _normalize_email(raw_email)
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not email:
            flash('A valid email is required.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif _find_user_by_email(email):
            flash('Email already registered. Please log in.', 'error')
            return redirect(url_for('login', email=email))
        else:
            user = User(
                name=name,
                email=email,
                password=generate_password_hash(password),
                is_admin=False,
            )
            db.session.add(user)
            db.session.commit()
            _start_user_session(user)
            flash('Account created — welcome to your portal!', 'success')
            return redirect(url_for('dashboard'))
    return render_template('register.html')


def _client_user_info(email):
    user = User.query.filter(db.func.lower(User.email) == _normalize_email(email)).first()
    return {
        'name': (user.name if user and user.name else email.split('@')[0]),
        'phone': user.phone if user else '',
        'email': email,
    }


def _build_dashboard_context(email):
    reports = Report.query.filter(
        db.func.lower(Report.user_email) == _normalize_email(email),
        Report.generated_report.isnot(None),
        Report.approved == True,
    ).order_by(Report.id.desc()).all()
    reports = [r for r in reports if _report_has_substantive_html(r)]
    documents = _get_client_documents(email)
    _ensure_document_labels(documents)
    latest_report = reports[0] if reports else None
    return {
        'reports': reports,
        'reports_by_date': _group_reports_by_date(reports),
        'documents': documents,
        'recommendations': get_personalized_recommendations(latest_report, documents),
        'stripe_ready': stripe_configured(),
        'user': _client_user_info(email),
    }


def _render_client_dashboard(email, admin_preview=False):
    return render_template(
        'dashboard.html',
        admin_preview=admin_preview,
        **_build_dashboard_context(email),
    )


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    email = session['email']

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_phone':
            user = User.query.get(session['user_id'])
            if user:
                user.phone = request.form.get('phone', '').strip()
                db.session.commit()
                flash('Phone number saved for SMS notifications.', 'success')
        elif action == 'upload':
            try:
                file_list = request.files.getlist('documents')
                if not any(f and f.filename for f in file_list):
                    file_list = request.files.getlist('document')
                upload_result = save_multiple_uploads(file_list, documents_dir)
                if isinstance(upload_result, tuple):
                    saved_files, partial_errors = upload_result
                else:
                    saved_files, partial_errors = upload_result, []

                upload_dt = datetime.now()
                form_date = request.form.get('test_date', '').strip()
                count = _save_client_documents(
                    email, saved_files, form_date=form_date, upload_dt=upload_dt,
                )
                db.session.commit()

                msg = f'Uploaded {count} file(s).'
                if _client_has_usable_scan_report(email):
                    msg += ' Click Request Updated Grok Analysis when you are ready.'
                else:
                    msg += ' Your practitioner will publish your bio scan report.'
                if partial_errors:
                    msg += f' Some files skipped: {"; ".join(partial_errors[:3])}'
                flash(msg, 'success')
            except ValueError as exc:
                flash(str(exc), 'error')
        elif action == 'request_analysis':
            report = _client_has_usable_scan_report(email)
            if report:
                report, doc_count, msgs = _regenerate_report_analysis(
                    report, notify_client=True, notify_admin=True
                )
                db.session.commit()
                flash(
                    f'Updated Grok analysis ready — used {doc_count} medical document(s). '
                    f'{" ".join(m for m in msgs if m)}',
                    'success',
                )
            else:
                flash('No scan report available yet. Contact your practitioner.', 'error')

    return _render_client_dashboard(email)


@app.route('/admin/client-portal')
def admin_client_portal():
    if not session.get('is_admin'):
        flash('Admin access required.', 'error')
        return redirect(url_for('login'))

    email = _normalize_email(request.args.get('email'))
    if not email:
        flash('Client email is required.', 'error')
        return redirect(url_for('admin'))

    return _render_client_dashboard(email, admin_preview=True)


@app.route('/reports/<int:report_id>')
def view_report(report_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    report = Report.query.get_or_404(report_id)
    if not _user_owns_report(report) or not report.generated_report:
        abort(403)
    if not session.get('is_admin') and not report.approved:
        abort(403)
    view = request.args.get('view', 'scan')
    if view not in ('scan', 'original', 'updates'):
        view = 'scan'
    return render_template(
        'report_view.html',
        report=report,
        view=view,
        user={'name': session.get('name', 'Client')},
    )


@app.route('/reports/<int:report_id>/pdf')
def download_report_pdf(report_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    report = Report.query.get_or_404(report_id)
    if not _user_owns_report(report):
        abort(403)
    if not session.get('is_admin') and not report.approved:
        abort(403)
    if not report.pdf_filename or not _report_has_substantive_html(report):
        flash(
            'This report has no scan findings yet — PDF download is not available.',
            'error',
        )
        return redirect(url_for('dashboard'))
    return send_from_directory(
        reports_dir,
        report.pdf_filename,
        as_attachment=True,
        download_name=f'{report.title}.pdf',
    )


@app.route('/admin/scan-pdf/<int:scan_id>')
def download_scan_pdf(scan_id):
    if not session.get('is_admin'):
        abort(403)
    scan = ReportScanPdf.query.get_or_404(scan_id)
    return send_from_directory(
        scan_pdfs_dir,
        scan.stored_filename,
        as_attachment=True,
        download_name=scan.original_name,
    )


@app.route('/documents/<int:doc_id>')
def download_document(doc_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    doc = ClientDocument.query.get_or_404(doc_id)
    if not session.get('is_admin') and _normalize_email(session.get('email')) != _normalize_email(doc.user_email):
        abort(403)
    return send_from_directory(
        documents_dir,
        doc.stored_filename,
        as_attachment=True,
        download_name=doc.original_name,
    )


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        flash('Admin access required.', 'error')
        return redirect(url_for('login'))

    latest_report = None

    selected_client = _normalize_email(request.args.get('client', ''))

    if request.method == 'POST':
        email = _resolve_client_email_from_form()
        client_pick = (request.form.get('client_email') or '').strip()
        if client_pick:
            selected_client = client_pick if client_pick == '__new__' else _normalize_email(client_pick)
        title = request.form.get('title', 'Full Scan').strip()
        raw_data = request.form.get('raw_data', '')
        action = request.form.get('action', 'generate')
        report_id = request.form.get('report_id')

        if action == 'upload_client_documents':
            doc_email = _normalize_email(request.form.get('doc_client_email', ''))
            if not doc_email:
                flash('Select a client to upload medical documents for.', 'error')
            else:
                try:
                    file_list = request.files.getlist('client_documents')
                    upload_result = save_multiple_uploads(file_list, documents_dir)
                    if isinstance(upload_result, tuple):
                        saved_files, partial_errors = upload_result
                    else:
                        saved_files, partial_errors = upload_result, []
                    count = _save_client_documents(
                        doc_email,
                        saved_files,
                        form_date=request.form.get('doc_test_date', '').strip(),
                    )
                    db.session.commit()
                    msg = f'Uploaded {count} medical document(s) to {doc_email} portal.'
                    if partial_errors:
                        msg += f' Some files skipped: {"; ".join(partial_errors[:3])}'
                    flash(msg, 'success')
                    selected_client = doc_email
                except ValueError as exc:
                    flash(str(exc), 'error')

        elif action == 'approve' and report_id:
            report = Report.query.get(report_id)
            if report and report.generated_report:
                send_email = request.form.get('send_email') == 'on'
                send_sms = request.form.get('send_sms') == 'on'
                msgs = _approve_and_send_report(report, send_email, send_sms)
                db.session.commit()
                flash(
                    f'Client notified for {report.user_email}. ' + ' '.join(msgs),
                    'success',
                )
            else:
                flash('Report not found or not yet generated.', 'error')

        elif action == 'refresh_original_grok' and report_id:
            report = Report.query.get(report_id)
            if _report_has_scan_data(report):
                report, msg = _refresh_original_grok_analysis(report)
                db.session.commit()
                flash(msg, 'success' if 'Grok original' in msg else 'error')
            else:
                flash('Report not found or missing scan data.', 'error')

        elif action == 'refresh_ai' and report_id:
            report = Report.query.get(report_id)
            if _report_has_scan_data(report):
                report, doc_count, _msgs = _regenerate_report_analysis(report)
                _publish_report_to_portal(report)
                db.session.commit()
                grok_err = get_last_grok_error()
                note = f' ({grok_err})' if grok_err else ''
                flash(
                    f'Updated Grok analysis republished to client portal '
                    f'({doc_count} medical document(s) included).{note}',
                    'success' if not grok_err else 'error',
                )
            else:
                flash('Report not found or missing raw data.', 'error')

        elif action == 'reconcile_blood' and report_id:
            report = Report.query.get(report_id)
            if _report_has_scan_data(report):
                report, doc_count, msgs = _apply_blood_reconciliation(report)
                _publish_report_to_portal(report)
                db.session.commit()
                flash(
                    f'Scan adjusted with blood tests for {report.user_email} '
                    f'({doc_count} document(s)). {" ".join(msgs)}',
                    'success',
                )
            else:
                flash('Report not found or missing scan data.', 'error')

        elif not email:
            flash('Select a client or enter a new client email.', 'error')
        else:
            pdf_errors = []
            try:
                combined_raw, pdf_results, pdf_errors = _process_admin_scan_input(raw_data)
            except ValueError as exc:
                flash(str(exc), 'error')
                combined_raw, pdf_results, pdf_errors = '', [], []

            if action == 'generate':
                if not (combined_raw or '').strip() and not pdf_results:
                    flash(
                        'No scan PDFs were received. Select 1.pdf, 2.pdf, and 3.pdf from '
                        'Documents\\Root Cause Test\\bio\\mp\\4-9-26\\ — not files from Downloads.',
                        'error',
                    )
                for upload_err in pdf_errors:
                    flash(upload_err, 'error')
                upload_summary = describe_pdf_uploads(pdf_results)
                if upload_summary:
                    flash(f'Scan PDFs received: {upload_summary}', 'success')
                for issue in scan_pdf_extraction_issues(pdf_results):
                    flash(issue, 'warning' if combined_raw and scan_text_has_content(combined_raw) else 'error')
                result = _create_published_scan_report(
                    email, title, combined_raw, pdf_results=pdf_results or None,
                )
                report = result[0]
                err = result[1]
                ai_source = result[2] if len(result) > 2 else 'local'
                grok_error = result[3] if len(result) > 3 else None
                if err:
                    flash(err, 'error')
                else:
                    db.session.commit()
                    _, doc_count = _medical_context(email)
                    latest_report = report
                    pdf_note = (
                        f' ({len(pdf_results)} scan PDF{"s" if len(pdf_results) != 1 else ""} processed)'
                        if pdf_results else ''
                    )
                    doc_note = (
                        f' Client has {doc_count} medical document(s) on file — '
                        f'they can request an updated Grok analysis anytime.'
                        if doc_count else ''
                    )
                    if ai_source == 'grok':
                        grok_note = ' Grok original scan analysis generated.'
                    elif grok_error:
                        grok_note = f' Grok unavailable ({grok_error}) — local scan summary used.'
                    else:
                        grok_note = ' Local scan summary generated.'
                    scan_chars = len(combined_raw or '')
                    if report.pdf_filename:
                        flash(
                            f'Original scan report published to {email} client portal.'
                            f'{grok_note}{doc_note} Scan text: {scan_chars} chars.{pdf_note}',
                            'success',
                        )
                    else:
                        flash(
                            f'Report published to client portal (PDF failed).{doc_note}{pdf_note}',
                            'error',
                        )
            elif action == 'save':
                if not combined_raw.strip():
                    flash('Paste raw scan data or upload at least one scan PDF.', 'error')
                else:
                    report = Report(
                        user_email=email,
                        title=title,
                        raw_data=combined_raw,
                        date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                    )
                    db.session.add(report)
                    db.session.commit()
                    if pdf_results:
                        _attach_scan_pdfs_to_report(report, pdf_results)
                        db.session.commit()
                    flash(
                        'Raw scan data saved to client record (admin-only visibility).',
                        'success',
                    )

    reports = Report.query.order_by(Report.id.desc()).all()
    client_scan_buckets = _group_clients_by_last_scan()
    clients = _get_clients_for_admin()
    client_groups = _split_clients_for_admin(clients)
    now = datetime.now().strftime('%b %d, %Y')
    return render_template(
        'admin.html',
        reports=reports,
        latest_report=latest_report,
        client_scan_buckets=client_scan_buckets,
        clients=clients,
        client_groups=client_groups,
        selected_client=selected_client,
        now=now,
    )


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


with app.app_context():
    db.create_all()
    migrate_schema()
    _normalize_stored_emails()
    ensure_admin_user()
    _backfill_empty_original_ai()
    _unpublish_empty_reports()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)