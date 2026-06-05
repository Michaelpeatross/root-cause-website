from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rootcause2026'

# Database fix for Render
basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/rootcause.db'
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
    user_email = db.Column(db.String(120))
    title = db.Column(db.String(200))
    generated_report = db.Column(db.Text)
    date = db.Column(db.String(50))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['email'] = email
            session['is_admin'] = user.is_admin
            flash('Login successful!')
            return redirect(url_for('admin' if user.is_admin else 'dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        flash('Admin access required')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        flash('Report received! (Generation coming soon)')
    
    return render_template('admin.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)