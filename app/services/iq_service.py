"""IQ test submission and non-LLM analysis."""

from app import db
from app.services.iq_test import generate_iq_summary


def submit_iq_test(user_id, data):
    db.save_iq_test_result(
        user_id,
        data.get('iq_score'),
        data.get('correct_count'),
        data.get('section_scores'),
        data.get('answers'),
        data.get('time_taken'),
    )

    summary = generate_iq_summary(data)

    return {
        'success': True,
        'iq_score': data.get('iq_score'),
        'section_scores': data.get('section_scores'),
        'ai_summary': summary,
    }
