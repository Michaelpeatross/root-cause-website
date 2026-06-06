from flask import (
    Flask, render_template, request, redirect, url_for, flash, session,
    send_from_directory, abort,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from collections import OrderedDict

from report_generator import generate_report_html, generate_report_text
from pdf_service import save_report_pdf, pdf_to_bytes

from document_service import (
    save_upload, save_multiple_uploads, extract_text, combined_document_text,
    process_scan_pdf_uploads, merge_scan_sources,
    parse_date_from_text, filter_recent_medical_documents,
)
from client_portal import get_personalized_recommendations
from health_advisor import get_health_recommendations
from notification_service import (
    notify_client_analysis_update, notify_admin_analysis_request,
    deliver_report_to_client,
)
from stripe_service import create_checkout_session, stripe_configured

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'rootcause2026secretkey')
app.config['MAX_CONTENT_LENGTH'] = 80 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
_site_https = os.environ.get('SITE_URL', '').startswith('https')
app.config['SESSION_COOKIE_SECURE'] = (
    os.environ.get('SESSION_COOKIE_SECURE', 'true' if _site_https else 'false').lower() == 'true'
)
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 14

basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')
uploads_dir = os.path.join(basedir, 'uploads')
reports_dir = os.path.join(uploads_dir, 'reports')
documents_dir = os.path.join(uploads_dir, 'documents')
scan_pdfs_dir = os.path.join(uploads_dir, 'scan_pdfs')
os.makedirs(instance_dir, exist_ok=True)
os.makedirs(reports_dir, exist_ok=True)
os.makedirs(documents_dir, exist_ok=True)
os.makedirs(scan_pdfs_dir, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "rootcause.db")}'
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


class ClientDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    stored_filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200))
    extracted_text = db.Column(db.Text)
    test_date = db.Column(db.String(20))
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
            }
            for col, col_type in new_cols.items():
                if col not in report_cols:
                    with db.engine.connect() as conn:
                        conn.execute(text(f'ALTER TABLE report ADD COLUMN {col} {col_type}'))
                        conn.commit()

    if 'client_document' in tables:
        doc_cols = {c['name'] for c in inspector.get_columns('client_document')}
        if 'test_date' not in doc_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE client_document ADD COLUMN test_date VARCHAR(20)'))
                conn.commit()

    if 'client_document' not in tables or 'report_scan_pdf' not in tables:
        db.create_all()


with app.app_context():
    db.create_all()
    migrate_schema()
    ensure_admin_user()


def _normalize_email(email):
    return (email or '').strip().lower()


def _user_owns_report(report):
    if session.get('is_admin'):
        return True
    return _normalize_email(session.get('email')) == _normalize_email(report.user_email)


def _get_client_documents(email):
    return ClientDocument.query.filter(
        db.func.lower(ClientDocument.user_email) == _normalize_email(email)
    ).order_by(ClientDocument.id.desc()).all()


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
    recent = filter_recent_medical_documents(docs)
    return combined_document_text(docs, recent_only=True), len(recent)


def _build_full_report(email, title, raw_data):
    """Generate HTML report with AI recommendations, PDF, and email."""
    medical_text, _doc_count = _medical_context(email)
    client_name = _client_display_name(email)

    ai_html, _source = get_health_recommendations(
        raw_data, medical_text, client_name, email
    )
    html_report = generate_report_html(email, title, raw_data, ai_html)
    plain_text = generate_report_text(email, title, raw_data, ai_html)
    return html_report, plain_text, ai_html


def _regenerate_report_analysis(report, notify_client=False, notify_admin=False):
    """Re-run Grok analysis using scan data + recent medical documents."""
    email = report.user_email
    medical_text, doc_count = _medical_context(email)
    client_name = _client_display_name(email)
    user = User.query.filter(db.func.lower(User.email) == _normalize_email(email)).first()

    ai_html, _ = get_health_recommendations(
        report.raw_data, medical_text, client_name, email
    )
    report.ai_recommendations = ai_html
    report.generated_report = generate_report_html(
        email, report.title, report.raw_data, ai_html
    )
    report.plain_text = generate_report_text(
        email, report.title, report.raw_data, ai_html
    )
    report.analysis_updated = datetime.now().strftime('%Y-%m-%d %H:%M')
    _save_pdf_for_report(report, report.generated_report)

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


def _process_admin_scan_input(pasted_text):
    """Handle pasted text plus any uploaded scan PDFs from the admin form."""
    pdf_results = process_scan_pdf_uploads(
        request.files.getlist('scan_pdfs'),
        scan_pdfs_dir,
    )
    combined = merge_scan_sources(pasted_text, pdf_results)
    return combined, pdf_results


def _save_pdf_for_report(report, html_report):
    pdf_name = f'report_{report.id}.pdf'
    pdf_path = os.path.join(reports_dir, pdf_name)
    if save_report_pdf(html_report, pdf_path):
        report.pdf_filename = pdf_name
        return True
    return False


def _approve_and_send_report(report, send_email=False, send_sms=False):
    """Mark report approved and deliver to client via selected channels."""
    user = User.query.filter(
        db.func.lower(User.email) == _normalize_email(report.user_email)
    ).first()
    client_name = _client_display_name(report.user_email)
    client_phone = user.phone if user else ''

    report.approved = True
    report.approved_at = datetime.now().strftime('%Y-%m-%d %H:%M')

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
        messages.append('Report approved and published to client portal (no notifications sent).')

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
    if not email:
        return None
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        user = User.query.filter(
            db.func.lower(User.email) == _normalize_email(email)
        ).first()
    return user


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
            session.permanent = True
            session['user_id'] = user.id
            session['email'] = user.email
            session['name'] = user.name or user.email.split('@')[0]
            session['is_admin'] = bool(user.is_admin)
            flash('Welcome back!', 'success')
            return redirect(url_for('admin') if user.is_admin else 'dashboard')

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
            flash('Incorrect password. Try again or use Forgot Password.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = _normalize_email(request.form.get('email'))
        password = request.form.get('password', '')
        if _find_user_by_email(email):
            flash('Email already registered. Please log in.', 'error')
        else:
            user = User(name=name, email=email, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


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
                    db.session.add(doc)
                    count += 1
                db.session.commit()

                msg = f'Uploaded {count} file(s). Recommendations updated from your latest scan + medical docs.'
                if partial_errors:
                    msg += f' Some files skipped: {"; ".join(partial_errors[:3])}'
                flash(msg, 'success')
            except ValueError as exc:
                flash(str(exc), 'error')
        elif action == 'request_analysis':
            report = Report.query.filter(
                db.func.lower(Report.user_email) == _normalize_email(email),
                Report.generated_report.isnot(None),
            ).order_by(Report.id.desc()).first()
            if report and report.raw_data:
                report, doc_count, msgs = _regenerate_report_analysis(
                    report, notify_client=True, notify_admin=True
                )
                db.session.commit()
                flash(
                    f'Updated Grok analysis sent! Used {doc_count} medical document(s) '
                    f'from the past year. {" ".join(m for m in msgs if m)}',
                    'success',
                )
            else:
                flash('No scan report available yet. Contact your practitioner.', 'error')

    reports = Report.query.filter(
        db.func.lower(Report.user_email) == _normalize_email(email),
        Report.generated_report.isnot(None),
        Report.approved == True,
    ).order_by(Report.id.desc()).all()
    documents = _get_client_documents(email)
    user_obj = User.query.get(session['user_id'])
    reports_by_date = _group_reports_by_date(reports)
    latest_report = reports[0] if reports else None
    recommendations = get_personalized_recommendations(latest_report, documents)

    return render_template(
        'dashboard.html',
        reports=reports,
        reports_by_date=reports_by_date,
        documents=documents,
        recommendations=recommendations,
        stripe_ready=stripe_configured(),
        user={
            'name': session.get('name', 'Client'),
            'phone': user_obj.phone if user_obj else '',
            'email': email,
        },
    )


@app.route('/reports/<int:report_id>')
def view_report(report_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    report = Report.query.get_or_404(report_id)
    if not _user_owns_report(report) or not report.generated_report:
        abort(403)
    if not session.get('is_admin') and not report.approved:
        abort(403)
    return render_template('report_view.html', report=report, user={'name': session.get('name', 'Client')})


@app.route('/reports/<int:report_id>/pdf')
def download_report_pdf(report_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    report = Report.query.get_or_404(report_id)
    if not _user_owns_report(report):
        abort(403)
    if not session.get('is_admin') and not report.approved:
        abort(403)
    if not report.pdf_filename:
        abort(404)
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

    if request.method == 'POST':
        email = _normalize_email(request.form.get('email'))
        title = request.form.get('title', 'Full Scan').strip()
        raw_data = request.form.get('raw_data', '')
        action = request.form.get('action', 'generate')
        report_id = request.form.get('report_id')

        if action == 'approve' and report_id:
            report = Report.query.get(report_id)
            if report and report.generated_report:
                send_email = request.form.get('send_email') == 'on'
                send_sms = request.form.get('send_sms') == 'on'
                msgs = _approve_and_send_report(report, send_email, send_sms)
                db.session.commit()
                flash(
                    f'Report approved for {report.user_email}. ' + ' '.join(msgs),
                    'success',
                )
            else:
                flash('Report not found or not yet generated.', 'error')

        elif action == 'refresh_ai' and report_id:
            report = Report.query.get(report_id)
            if report and report.raw_data:
                was_approved = report.approved
                report, doc_count, _msgs = _regenerate_report_analysis(report)
                if was_approved:
                    report.approved = False
                db.session.commit()
                flash(
                    f'AI recommendations refreshed ({doc_count} recent medical doc(s) included). '
                    f'{"Re-approve to send updates to client." if was_approved else "Review and approve to send."}',
                    'success',
                )
            else:
                flash('Report not found or missing raw data.', 'error')

        elif not email:
            flash('Client email is required.', 'error')
        else:
            try:
                combined_raw, pdf_results = _process_admin_scan_input(raw_data)
            except ValueError as exc:
                flash(str(exc), 'error')
                combined_raw, pdf_results = '', []

            if action == 'generate':
                if not combined_raw.strip():
                    flash('Paste raw scan data or upload at least one scan PDF.', 'error')
                else:
                    html_report, plain_text, ai_html = _build_full_report(
                        email, title, combined_raw
                    )
                    report = Report(
                        user_email=email,
                        title=title,
                        raw_data=combined_raw,
                        generated_report=html_report,
                        plain_text=plain_text,
                        ai_recommendations=ai_html,
                        approved=False,
                        date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                    )
                    db.session.add(report)
                    db.session.commit()

                    if pdf_results:
                        _attach_scan_pdfs_to_report(report, pdf_results)
                        db.session.commit()

                    pdf_ok = _save_pdf_for_report(report, html_report)
                    db.session.commit()

                    latest_report = report
                    pdf_note = (
                        f' ({len(pdf_results)} scan PDF{"s" if len(pdf_results) != 1 else ""} processed)'
                        if pdf_results else ''
                    )
                    if pdf_ok:
                        flash(
                            f'Report generated for review — NOT sent to client yet. '
                            f'Check email/text boxes and click Approve & Send.{pdf_note}',
                            'success',
                        )
                    else:
                        flash(f'Report generated (PDF failed). Review and approve before sending.{pdf_note}', 'error')
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
    now = datetime.now().strftime('%b %d, %Y')
    return render_template(
        'admin.html',
        reports=reports,
        latest_report=latest_report,
        now=now,
    )


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)