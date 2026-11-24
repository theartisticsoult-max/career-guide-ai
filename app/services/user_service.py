"""User, dashboard and admin data operations."""

from app import db


def authenticate_user(username, password):
    return db.authenticate_user(username, password)


def register_user(username, email, password, full_name, phone, education, stream):
    return db.create_user(username, email, password, full_name, phone, education, stream)


def get_user(user_id):
    return db.get_user_by_id(user_id)


def is_admin(user_id):
    user = db.get_user_by_id(user_id)
    return bool(user and user.get('is_admin'))


def get_dashboard_data(user_id):
    """Assemble everything the dashboard template needs."""
    return {
        'user': db.get_user_by_id(user_id),
        'psychometric_results': db.get_psychometric_results(user_id, limit=1),
        'quiz_results': db.get_quiz_results(user_id, limit=1),
        'iq_results': db.get_iq_test_results(user_id, limit=1),
        'iq_stats': db.get_iq_test_stats(user_id),
    }


def get_admin_dashboard_data():
    """Assemble everything the admin dashboard template needs."""
    return {
        'stats': db.get_stats(),
        'users': db.get_all_users(),
        'logs': db.get_admin_logs(),
    }


def get_admin_user_data(user_id):
    """Assemble everything the admin user detail template needs."""
    return {
        'user': db.get_user_by_id(user_id),
        'psychometric_results': db.get_psychometric_results(user_id),
        'quiz_results': db.get_quiz_results(user_id),
    }


def delete_user(admin_id, user_id):
    """Delete a user and record the admin action."""
    db.delete_user(user_id)
    db.log_admin_action(admin_id, f'Deleted user {user_id}', user_id)
