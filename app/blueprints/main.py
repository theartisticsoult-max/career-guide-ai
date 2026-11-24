"""Public pages and assessment pages."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.blueprints.auth import login_required
from app.services import (
    assessment_service,
    career_data,
    profile_service,
    recommendation_service,
    user_service,
)
from data.assessment_questions import (
    APTITUDE_QUESTIONS,
    INTEREST_STATEMENTS,
    PREFERENCE_QUESTIONS,
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


@main_bp.route('/assessment', methods=['GET', 'POST'])
@login_required
def assessment():
    """Combined three-part assessment with resume support."""
    user_id = session['user_id']
    state = assessment_service.get_state(user_id)
    if state['status'] == 'completed':
        return redirect(url_for('main.dashboard'))

    try:
        part = int(request.args.get('part', state['current_part']))
    except (TypeError, ValueError):
        part = state['current_part']
    part = max(1, min(3, part))

    if request.method == 'POST':
        try:
            submitted_part = int(request.form.get('part', part))
        except (TypeError, ValueError):
            submitted_part = part
        submitted_part = max(1, min(3, submitted_part))

        answers = {}
        if submitted_part == 1:
            for question in INTEREST_STATEMENTS:
                value = request.form.get(question['id'])
                if value and value.isdigit() and 1 <= int(value) <= 5:
                    answers[question['id']] = int(value)
        elif submitted_part == 2:
            for question in APTITUDE_QUESTIONS:
                value = request.form.get(question['id'])
                if value and value.isdigit() and int(value) < len(question['options']):
                    answers[question['id']] = int(value)
        else:
            allowed = {
                question['id']: [option['value'] for option in question['options']]
                for question in PREFERENCE_QUESTIONS
            }
            for key, values in allowed.items():
                value = request.form.get(key)
                if value in values:
                    answers[key] = value

        if not answers:
            flash('Please answer at least one question.', 'error')
            return redirect(url_for('main.assessment', part=submitted_part))

        assessment_service.save_part(user_id, state['assessment_id'], submitted_part, answers)
        if submitted_part == 3:
            combined = assessment_service.get_answers(user_id, state['assessment_id'])
            assessment_service.complete(user_id, state['assessment_id'], combined)
            flash('Assessment complete! Here are your career matches.', 'success')
            return redirect(url_for('main.recommendations'))
        return redirect(url_for('main.assessment', part=submitted_part + 1))

    return render_template(
        'assessment.html',
        part=part,
        questions=assessment_service.questions_for_part(part),
        saved=assessment_service.get_answers(user_id, state['assessment_id']),
        progress=int((part - 1) / 3 * 100),
    )


@main_bp.route('/recommendations')
@login_required
def recommendations():
    """Show code-ranked careers from the user's latest assessment."""
    result = recommendation_service.get_recommendations(session['user_id'])
    if result['needs_assessment']:
        flash('Complete the assessment first to see your career matches.', 'error')
        return redirect(url_for('main.assessment'))
    return render_template(
        'recommendations.html',
        recommendations=result['items'],
        chosen=result['chosen'],
    )


@main_bp.route('/recommendations/choose', methods=['POST'])
@login_required
def choose_recommendation():
    """Record a career chosen from the recommendations list."""
    result = recommendation_service.choose_career(
        session['user_id'], request.form.get('career_id', '')
    )
    if result['success']:
        flash('Career saved! You can now build your roadmap.', 'success')
    else:
        flash(result['error'], 'error')
    return redirect(url_for('main.recommendations'))


@main_bp.route('/quiz')
@login_required
def quiz():
    """Legacy quiz now enters the combined assessment."""
    return redirect(url_for('main.assessment'))


@main_bp.route('/psychometric-test')
@login_required
def psychometric_test():
    """Legacy psychometric test now enters the combined assessment."""
    return redirect(url_for('main.assessment'))


@main_bp.route('/results')
@login_required
def results():
    """Legacy results page now enters the combined assessment."""
    return redirect(url_for('main.assessment'))


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
    """Legacy results now enter the combined assessment."""
    return redirect(url_for('main.assessment'))


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
    """Legacy IQ test now enters the combined assessment."""
    return redirect(url_for('main.assessment'))


@main_bp.route('/iq-test-results')
@login_required
def iq_test_results():
    """Legacy results now enter the combined assessment."""
    return redirect(url_for('main.assessment'))


@main_bp.route('/health')
def health_check():
    return {'status': 'healthy', 'message': 'Career Guide AI is running'}
