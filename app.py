from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rootcause2026'

# Simple in-memory storage for now (to avoid database issues on Render)
users = {}
reports = []

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
        user = users.get(email)
        if user and user['password'] == password:
            session['email'] = email
            session['is_admin'] = user.get('is_admin', False)
            flash('Logged in successfully!')
            return redirect(url_for('admin' if session['is_admin'] else 'dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        flash('Admin access only')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        title = request.form.get('title')
        raw_data = request.form.get('raw_data', '')
        flash('✅ Report processed! (Generation coming soon)')
        reports.append({'email': email, 'title': title, 'data': raw_data})
    
    return render_template('admin.html', reports=reports)

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)