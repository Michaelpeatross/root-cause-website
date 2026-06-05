from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

from report_generator import generate_report_html

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'rootcause2026secretkey')

basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')
os.makedirs(instance_dir, exist_ok=True)
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
    date = db.Column(db.String(50))


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


with app.app_context():
    db.create_all()
    migrate_schema()
    ensure_admin_user()


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
        email = request.form.get('email', '').strip().lower()
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
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please log in.', 'error')
        else:
            user = User(
                name=name,
                email=email,
                password=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    reports = Report.query.filter_by(user_email=session['email']).order_by(Report.id.desc()).all()
    return render_template(
        'dashboard.html',
        reports=reports,
        user={'name': session.get('name', 'Client')},
    )


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        flash('Admin access required.', 'error')
        return redirect(url_for('login'))

    latest_report = None

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        title = request.form.get('title', 'Full Scan').strip()
        raw_data = request.form.get('raw_data', '')
        action = request.form.get('action', 'generate')

        if not email:
            flash('Client email is required.', 'error')
        elif action == 'generate':
            if not raw_data.strip():
                flash('Paste raw scan data before generating a report.', 'error')
            else:
                html_report = generate_report_html(email, title, raw_data)
                report = Report(
                    user_email=email,
                    title=title,
                    raw_data=raw_data,
                    generated_report=html_report,
                    date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                )
                db.session.add(report)
                db.session.commit()
                latest_report = report
                flash('Report generated successfully!', 'success')
        else:
            report = Report(
                user_email=email,
                title=title,
                raw_data=raw_data,
                date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            )
            db.session.add(report)
            db.session.commit()
            flash('Raw scan data saved.', 'success')

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