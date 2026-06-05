from flask import (
    Flask, render_template, request, redirect, url_for, flash, session,
    send_from_directory, abort,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

from report_generator import generate_report_html, generate_report_text
from pdf_service import save_report_pdf, pdf_to_bytes
from email_service import send_report_email
from document_service import save_upload, extract_text, combined_document_text
from health_advisor import get_health_recommendations

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'rootcause2026secretkey')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')
uploads_dir = os.path.join(basedir, 'uploads')
reports_dir = os.path.join(uploads_dir, 'reports')
documents_dir = os.path.join(uploads_dir, 'documents')
os.makedirs(instance_dir, exist_ok=True)
os.makedirs(reports_dir, exist_ok=True)
os.makedirs(documents_dir, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "rootcause.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200))
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
    date = db.Column(db.String(50))


class ClientDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    stored_filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200))
    extracted_text = db.Column(db.Text)
    uploaded_at = db.Column(db.String(50))


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
        if 'is_admin' not in user_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0'))
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
            }
            for col, col_type in new_cols.items():
                if col not in report_cols:
                    with db.engine.connect() as conn:
                        conn.execute(text(f'ALTER TABLE report ADD COLUMN {col} {col_type}'))
                        conn.commit()

    if 'client_document' not in tables:
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


def _build_full_report(email, title, raw_data):
    """Generate HTML report with AI recommendations, PDF, and email."""
    docs = _get_client_documents(email)
    medical_text = combined_document_text(docs)
    client_name = _client_display_name(email)

    ai_html, _source = get_health_recommendations(
        raw_data, medical_text, client_name, email
    )
    html_report = generate_report_html(email, title, raw_data, ai_html)
    plain_text = generate_report_text(email, title, raw_data, ai_html)
    return html_report, plain_text, ai_html


def _save_pdf_for_report(report, html_report):
    pdf_name = f'report_{report.id}.pdf'
    pdf_path = os.path.join(reports_dir, pdf_name)
    if save_report_pdf(html_report, pdf_path):
        report.pdf_filename = pdf_name
        return True
    return False


def _email_report_to_client(report, html_report, plain_text):
    pdf_bytes = pdf_to_bytes(html_report)
    safe_title = report.title.replace('/', '-')[:60]
    subject = f'Your Root Cause Report: {report.title}'
    ok, msg = send_report_email(
        report.user_email,
        subject,
        plain_text,
        pdf_bytes=pdf_bytes,
        pdf_filename=f'{safe_title}.pdf',
    )
    report.email_sent = ok
    return ok, msg


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/buy')
def buy():
    return render_template('buy.html')


@app.route('/instructions')
def instructions():
    return render_template('instructions.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = _normalize_email(request.form.get('email'))
        password = request.form.get('password', '')
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['email'] = user.email
            session['name'] = user.name or user.email.split('@')[0]
            session['is_admin'] = user.is_admin
            flash('Welcome back!', 'success')
            return redirect(url_for('admin') if user.is_admin else 'dashboard')
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = _normalize_email(request.form.get('email'))
        password = request.form.get('password', '')
        if User.query.filter(db.func.lower(User.email) == email).first():
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
        if action == 'upload':
            try:
                stored, original = save_upload(
                    request.files.get('document'),
                    documents_dir,
                )
                path = os.path.join(documents_dir, stored)
                text = extract_text(path, original)
                doc = ClientDocument(
                    user_email=email,
                    stored_filename=stored,
                    original_name=original,
                    extracted_text=text,
                    uploaded_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                )
                db.session.add(doc)
                db.session.commit()
                flash(f'Uploaded: {original}', 'success')
            except ValueError as exc:
                flash(str(exc), 'error')
        elif action == 'refresh_ai':
            report = Report.query.filter(
                db.func.lower(Report.user_email) == _normalize_email(email),
                Report.generated_report.isnot(None),
            ).order_by(Report.id.desc()).first()
            if report and report.raw_data:
                docs = _get_client_documents(email)
                medical_text = combined_document_text(docs)
                ai_html, _ = get_health_recommendations(
                    report.raw_data,
                    medical_text,
                    session.get('name', 'Client'),
                    email,
                )
                report.ai_recommendations = ai_html
                report.generated_report = generate_report_html(
                    email, report.title, report.raw_data, ai_html
                )
                report.plain_text = generate_report_text(
                    email, report.title, report.raw_data, ai_html
                )
                if _save_pdf_for_report(report, report.generated_report):
                    db.session.commit()
                    flash('Health recommendations updated with your latest documents.', 'success')
                else:
                    db.session.commit()
                    flash('Recommendations updated (PDF regeneration failed).', 'error')
            else:
                flash('No report available to update yet.', 'error')

    reports = Report.query.filter(
        db.func.lower(Report.user_email) == _normalize_email(email)
    ).order_by(Report.id.desc()).all()
    documents = _get_client_documents(email)

    return render_template(
        'dashboard.html',
        reports=reports,
        documents=documents,
        user={'name': session.get('name', 'Client')},
    )


@app.route('/reports/<int:report_id>/pdf')
def download_report_pdf(report_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    report = Report.query.get_or_404(report_id)
    if not _user_owns_report(report):
        abort(403)
    if not report.pdf_filename:
        abort(404)
    return send_from_directory(
        reports_dir,
        report.pdf_filename,
        as_attachment=True,
        download_name=f'{report.title}.pdf',
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

        if action == 'refresh_ai' and report_id:
            report = Report.query.get(report_id)
            if report and report.raw_data:
                docs = _get_client_documents(report.user_email)
                medical_text = combined_document_text(docs)
                ai_html, _ = get_health_recommendations(
                    report.raw_data,
                    medical_text,
                    _client_display_name(report.user_email),
                    report.user_email,
                )
                report.ai_recommendations = ai_html
                report.generated_report = generate_report_html(
                    report.user_email, report.title, report.raw_data, ai_html
                )
                report.plain_text = generate_report_text(
                    report.user_email, report.title, report.raw_data, ai_html
                )
                _save_pdf_for_report(report, report.generated_report)
                db.session.commit()
                flash('AI recommendations refreshed for this client.', 'success')
            else:
                flash('Report not found or missing raw data.', 'error')

        elif not email:
            flash('Client email is required.', 'error')
        elif action == 'generate':
            if not raw_data.strip():
                flash('Paste raw scan data before generating a report.', 'error')
            else:
                html_report, plain_text, ai_html = _build_full_report(email, title, raw_data)
                report = Report(
                    user_email=email,
                    title=title,
                    raw_data=raw_data,
                    generated_report=html_report,
                    plain_text=plain_text,
                    ai_recommendations=ai_html,
                    date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                )
                db.session.add(report)
                db.session.commit()

                pdf_ok = _save_pdf_for_report(report, html_report)
                email_ok, email_msg = _email_report_to_client(report, html_report, plain_text)
                db.session.commit()

                latest_report = report
                if pdf_ok and email_ok:
                    flash(f'Report saved to client portal, PDF created, and emailed to {email}.', 'success')
                elif pdf_ok:
                    flash(f'Report saved and PDF created. {email_msg}', 'error')
                else:
                    flash(f'Report saved to portal. PDF/email issue: {email_msg}', 'error')
        else:
            report = Report(
                user_email=email,
                title=title,
                raw_data=raw_data,
                date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            )
            db.session.add(report)
            db.session.commit()
            flash('Raw scan data saved to client record (admin-only visibility).', 'success')

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