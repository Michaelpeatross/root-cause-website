from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rootcause2026secretkeychangeinproduction'

# Better database path for Render
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

with app.app_context():
    db.create_all()

# ==================== ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buy')
def buy():
    return render_template('buy.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['email'] = user.email
            session['is_admin'] = user.is_admin
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin' if user.is_admin else 'dashboard'))
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(email=email).first():
            flash('Email already exists. Please login.', 'error')
        else:
            hashed = generate_password_hash(password)
            user = User(name=name, email=email, password=hashed)
            db.session.add(user)
            db.session.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    reports = Report.query.filter_by(user_email=session['email']).all()
    return render_template('dashboard.html', reports=reports, email=session.get('email'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Admin access only', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        title = request.form.get('title')
        raw_data = request.form.get('raw_data', '')
        action = request.form.get('action')

        if action == 'generate':
            generated_report = f"""🌿 Root Cause Bioenergetic Analysis Report
========================================

Client: {email}
Title: {title}
Date: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

**Key Findings**
{raw_data[:700] if raw_data else 'Raw scan data will appear here...'}

**Main Areas of Imbalance**
• Digestive system
• Nervous system stress
• Microbial patterns
• Nutritional markers

**Supplement Recommendations**
• Zinc, Digestive Enzymes, Milk Thistle, Omega-3, Magnesium

**Recommended Blood Tests**
• Thyroid Panel, Zinc, Vitamin D, Inflammatory markers

Full report ready for delivery.
"""
            report = Report(user_email=email, title=title, raw_data=raw_data, generated_report=generated_report, date=datetime.now().strftime('%Y-%m-%d %H:%M'))
            db.session.add(report)
            db.session.commit()
            flash('✅ Easy-to-read report generated!', 'success')
        else:
            report = Report(user_email=email, title=title, raw_data=raw_data, date=datetime.now().strftime('%Y-%m-%d %H:%M'))
            db.session.add(report)
            db.session.commit()
            flash('Raw data saved.', 'success')

    reports = Report.query.all()
    return render_template('admin.html', reports=reports)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)