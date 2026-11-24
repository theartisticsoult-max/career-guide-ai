"""JSON APIs. Routes validate input and delegate to services."""
from flask import Blueprint, current_app, jsonify, request, session

from app import limiter
from app.blueprints.auth import login_required
from app.services import career_data, chatbot_service
from app.services.iq_service import submit_iq_test
from app.services.psychometric_service import submit_psychometric
from app.services.quiz_service import submit_quiz

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/quiz/submit', methods=['POST'])
@login_required
def quiz_submit():
    try:
        result = submit_quiz(session['user_id'], request.json)
        return jsonify(result)
    except Exception:
        current_app.logger.exception('Error in submit_quiz')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_bp.route('/api/psychometric/submit', methods=['POST'])
@login_required
def psychometric_submit():
    try:
        result = submit_psychometric(session['user_id'], request.json)
        return jsonify(result)
    except Exception:
        current_app.logger.exception('Error in submit_psychometric')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_bp.route('/api/chatbot', methods=['POST'])
@limiter.limit('20/minute')
def api_chatbot():
    try:
        data = request.json or {}
        message = data.get('message', '').strip()
        history = data.get('history', [])

        if not message:
            return jsonify({'response': "Please enter a question or message."}), 400

        response = chatbot_service.get_chatbot_response(
            message, history=history, career_df=career_data.career_df
        )
        return jsonify({'response': response})
    except Exception:
        current_app.logger.exception('Chatbot error')
        return jsonify({'response': "I'm having trouble processing your request. Please try again later."}), 500


@api_bp.route('/api/all-careers')
def all_careers():
    return jsonify(career_data.get_all_careers())


@api_bp.route('/api/featured-careers')
def featured_careers():
    return jsonify(career_data.get_featured_careers())


@api_bp.route('/api/categories')
def categories():
    return jsonify(career_data.get_categories())


@api_bp.route('/api/category/<category>')
def category(category):
    return jsonify(career_data.get_careers_by_category(category))


@api_bp.route('/api/career/<career_id>')
def career(career_id):
    if not career_data.is_loaded():
        return jsonify({'error': 'Data not loaded'}), 500

    career_record = career_data.get_career(career_id)
    if career_record is None:
        return jsonify({'error': 'Career not found'}), 404

    return jsonify(career_record)


@api_bp.route('/api/compare', methods=['POST'])
def compare():
    career_ids = request.json.get('career_ids', [])
    return jsonify({'careers': career_data.compare_careers(career_ids)})


@api_bp.route('/api/search')
def search():
    return jsonify(career_data.search_careers(request.args.get('q', '')))


@api_bp.route('/api/iq-test/submit', methods=['POST'])
@login_required
def iq_test_submit():
    """Save IQ test results"""
    try:
        result = submit_iq_test(session['user_id'], request.json)
        return jsonify(result)
    except Exception:
        current_app.logger.exception('Error in submit_iq_test')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
