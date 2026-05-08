"""
Authentication: single-admin session-based login.
Public routes are accessible without login; admin routes require session flag.
"""
import os
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, current_app)
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """Decorator that redirects unauthenticated requests to the login page."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated


def _hash_file_path():
    return current_app.config.get('ADMIN_HASH_FILE',
                                  os.path.join(current_app.instance_path, 'admin.hash'))


def _save_password_hash(new_hash):
    """Persist the admin password hash to disk. No-op in test mode."""
    if current_app.config.get('TESTING'):
        return
    with open(_hash_file_path(), 'w') as f:
        f.write(new_hash)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        if check_password_hash(current_app.config['ADMIN_PASSWORD_HASH'], password):
            session['admin_logged_in'] = True
            session.permanent = False
            flash('Logged in as administrator.', 'success')
            next_url = request.form.get('next') or url_for('main.dashboard')
            return redirect(next_url)
        flash('Incorrect password.', 'danger')

    next_url = request.args.get('next', '')
    return render_template('auth/login.html', next=next_url)


@auth_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Logged out.', 'info')
    return redirect(url_for('main.welcome'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=request.path))

    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not check_password_hash(current_app.config['ADMIN_PASSWORD_HASH'], current_pw):
            flash('Current password is incorrect.', 'danger')
        elif not new_pw:
            flash('New password cannot be empty.', 'danger')
        elif new_pw != confirm_pw:
            flash('New passwords do not match.', 'danger')
        else:
            new_hash = generate_password_hash(new_pw)
            current_app.config['ADMIN_PASSWORD_HASH'] = new_hash
            _save_password_hash(new_hash)
            flash('Password changed successfully.', 'success')
            return redirect(url_for('main.dashboard'))

    return render_template('auth/change_password.html')
