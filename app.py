from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rootcause2026'

# In-memory storage (no database issues)
users = {
    'michaelpeatross@gmail.com': {
        'name': 'Michael Peatross',
        'password': 'admin123',
        'is_admin': True
    }
}
reports = []

@app.route('/')
def index():
    return render_template_string('''
    <h1>Root Cause</h1>
    <p>Bioenergetic Hair Analysis</p>
    <a href="/buy"><button>Get Your Analysis - $199</button></a>
    <a href="/login"><button>Current Customer Login</button></a>
    ''')

@app.route('/buy')
def buy():
    return render_template_string('''
    <h1>Purchase Page</h1>
    <p>$199 with $30 off</p>
    <button onclick="alert('Checkout coming soon!')">Proceed to Checkout</button>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = users.get(email)
        if user and user['password'] == password:
            session['email'] = email
            session['is_admin'] = user['is_admin']
            flash('Login successful!')
            return redirect(url_for('admin' if user['is_admin'] else 'dashboard'))
        flash('Invalid credentials')
    
    return render_template_string('''
    <h2>Login</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <p style="color:red">{{ messages[0] }}</p>
      {% endif %}
    {% endwith %}
    <form method="POST">
        <input type="email" name="email" placeholder="Email" required><br><br>
        <input type="password" name="password" placeholder="Password" required><br><br>
        <button type="submit">Login</button>
    </form>
    <p>Use: michaelpeatross@gmail.com / admin123</p>
    ''')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        flash('Report received and processed!')
        reports.append(request.form.get('raw_data'))
    
    return render_template_string('''
    <h1>Admin Panel - Michael Peatross</h1>
    <form method="POST">
        <textarea name="raw_data" rows="10" cols="80" placeholder="Paste raw scan data here..."></textarea><br><br>
        <button type="submit">Generate Report</button>
    </form>
    <p>Reports processed: {{ reports|length }}</p>
    <a href="/logout">Logout</a>
    ''', reports=reports)

@app.route('/dashboard')
def dashboard():
    return "<h1>Client Dashboard - Coming Soon</h1>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)