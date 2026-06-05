from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'rootcause2026secretkey'
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
    user_email = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    date = db.Column(db.String(50))

with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buy')
def buy():
    return render_template('buy.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['email'] = user.email
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
        else:
            hashed = generate_password_hash(password)
            user = User(name=name, email=email, password=hashed)
            db.session.add(user)
            db.session.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    reports = Report.query.filter_by(user_email=session['email']).all()
    return render_template('dashboard.html', reports=reports)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        email = request.form['email']
        title = request.form['title']
        content = request.form['content']
        report = Report(user_email=email, title=title, content=content, date="Just now")
        db.session.add(report)
        db.session.commit()
        flash('Report uploaded successfully!', 'success')
    
    reports = Report.query.all()
    return render_template('admin.html', reports=reports)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)