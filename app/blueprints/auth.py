"""Login, registration, logout and access decorators."""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app import limiter
from app.services import user_service

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def logout_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' in session:
            flash('You are already logged in', 'info')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if not user_service.is_admin(session['user_id']):
            flash('Admin access required', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('5/minute')
@logout_required
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = user_service.authenticate_user(username, password)

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']

            flash('Login successful! Welcome back!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@logout_required
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        education = request.form.get('education')
        stream = request.form.get('stream')

        # Validate inputs
        if not username or not email or not password:
            flash('Please fill in all required fields', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('register.html')

        result = user_service.register_user(
            username, email, password, full_name, phone, education, stream
        )

        if result['success']:
            flash('Registration successful! Please login to continue.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(f'Registration failed: {result["error"]}', 'error')

    return render_template('register.html')


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('main.index'))
