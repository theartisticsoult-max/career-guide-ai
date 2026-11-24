"""Admin pages."""
from flask import Blueprint, flash, redirect, render_template, session, url_for

from app.blueprints.auth import admin_required
from app.services import user_service

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html', **user_service.get_admin_dashboard_data())


@admin_bp.route('/admin/user/<int:user_id>')
@admin_required
def admin_view_user(user_id):
    return render_template('admin_user.html', **user_service.get_admin_user_data(user_id))


@admin_bp.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user_service.delete_user(session['user_id'], user_id)
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin.admin_dashboard'))
