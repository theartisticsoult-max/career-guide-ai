"""Public pages and assessment pages."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.blueprints.auth import login_required
from app.services import career_data, profile_service, user_service
from data.questions import (
    PERSONALITY_QUESTIONS,
    INTEREST_QUESTIONS,
    APTITUDE_QUESTIONS,
    WORK_STYLE_QUESTIONS,
    VALUES_QUESTIONS,
    IQ_LOGICAL_QUESTIONS,
    IQ_NUMERICAL_QUESTIONS,
    IQ_VERBAL_QUESTIONS,
    IQ_SPATIAL_QUESTIONS,
    IQ_MEMORY_QUESTIONS,
)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page"""
    categories = career_data.get_categories()
    return render_template(
        'index.html',
        categories=categories,
        user_logged_in='user_id' in session,
    )


@main_bp.route('/categories')
def all_categories():
    """Show all career categories - Public access"""
    if not career_data.is_loaded():
        return "Error loading data", 500
    return render_template('categories.html', categories=career_data.get_categories())


@main_bp.route('/category/<category>')
def category_page(category):
    """Category page - Public access"""
    if not career_data.is_loaded():
        return "Error loading data", 500
    if not career_data.is_valid_category(category):
        return render_template('404.html'), 404
    return render_template('category.html', category=category)


@main_bp.route('/chatbot')
def chatbot():
    """AI chatbot page"""
    return render_template('chatbot.html')


@main_bp.route('/resources')
def resources():
    """Learning resources page."""
    return render_template('resources.html')


@main_bp.route('/quiz')
@login_required
def quiz():
    """Career assessment quiz - Login required"""
    return render_template('quiz.html')


@main_bp.route('/psychometric-test')
@login_required
def psychometric_test():
    """Psychometric assessment test page - Login required"""
    return render_template('psychometric_test.html',
                           personality_questions=PERSONALITY_QUESTIONS,
                           interest_questions=INTEREST_QUESTIONS,
                           aptitude_questions=APTITUDE_QUESTIONS,
                           work_style_questions=WORK_STYLE_QUESTIONS,
                           values_questions=VALUES_QUESTIONS)


@main_bp.route('/results')
@login_required
def results():
    return render_template('results.html')


@main_bp.route('/career/<career_id>')
def career_detail(career_id):
    if not career_data.is_loaded():
        return "Error loading data", 500

    career = career_data.get_career(career_id)
    if career is None:
        return render_template('404.html'), 404

    return render_template(
        'career.html',
        career=career,
        similar=career_data.get_similar_careers(career_id, top_n=4),
    )


@main_bp.route('/compare')
def compare():
    if not career_data.is_loaded():
        return "Error loading data", 500
    requested_ids = [cid.strip() for cid in request.args.get('ids', '').split(',') if cid.strip()]
    selected_ids = [cid for cid in requested_ids if career_data.get_career(cid) is not None][:3]
    return render_template(
        'compare.html',
        careers=career_data.get_compare_options(),
        selected_ids=selected_ids,
    )


@main_bp.route('/psychometric-results')
@login_required
def psychometric_results():
    """Display psychometric assessment results - Login required"""
    return render_template('psychometric_results.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    return render_template('dashboard.html', **user_service.get_dashboard_data(session['user_id']))


@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """One-time profile form shown after registration."""
    user_id = session['user_id']
    if request.method == 'POST':
        stage = request.form.get('stage', '').strip()
        if stage not in profile_service.STAGES:
            flash('Please choose a valid class stage.', 'error')
            return redirect(url_for('main.profile'))
        result = profile_service.save_profile(
            user_id,
            stage,
            stream=request.form.get('stream', '').strip(),
            interests_text=request.form.get('interests_text', '').strip(),
            city=request.form.get('city', '').strip(),
        )
        if not result['success']:
            flash(result['error'], 'error')
            return redirect(url_for('main.profile'))
        flash('Profile saved!', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('profile.html', profile=profile_service.get_profile(user_id))


@main_bp.route('/iq-test')
@login_required
def iq_test():
    """IQ Test page"""
    return render_template('iq_test.html',
                           logical_questions=IQ_LOGICAL_QUESTIONS,
                           numerical_questions=IQ_NUMERICAL_QUESTIONS,
                           verbal_questions=IQ_VERBAL_QUESTIONS,
                           spatial_questions=IQ_SPATIAL_QUESTIONS,
                           memory_questions=IQ_MEMORY_QUESTIONS)


@main_bp.route('/iq-test-results')
@login_required
def iq_test_results():
    """IQ Test results page"""
    return render_template('iq_test_results.html')


@main_bp.route('/health')
def health_check():
    return {'status': 'healthy', 'message': 'Career Guide AI is running'}
