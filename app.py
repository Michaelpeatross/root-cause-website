from flask import Flask, request, redirect, url_for, flash, session, render_template
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rootcause2026secret'

# In-memory storage
reports = []

@app.route('/')
def index():
    return "<h1>Welcome to Root Cause</h1><a href='/admin'>Go to Admin</a>"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if email == 'michaelpeatross@gmail.com' and password == 'admin123':
            session['email'] = email
            session['is_admin'] = True
            return redirect(url_for('admin'))
        flash('Invalid login')
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        title = request.form.get('title', 'Full Scan')
        raw_data = request.form.get('raw_data', '')
        
        # Simple report generation
        generated = f"""ROOT CAUSE BIOENERGETIC REPORT
Title: {title}
Client: {email}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

SUMMARY:
{raw_data[:500]}...

KEY FINDINGS:
• Digestive stress detected
• Possible microbial imbalances
• Recommend further testing

SUPPLEMENTS SUGGESTED:
• Probiotics, Digestive enzymes, Zinc

RECOMMENDED BLOOD TESTS:
• Comprehensive Stool Test, CBC, Vitamin levels
"""
        
        reports.append({
            'title': title,
            'email': email,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'generated_report': generated
        })
        
        flash('✅ Report generated successfully!')
    
    return render_template('admin.html', reports=reports)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)