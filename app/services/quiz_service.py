"""Career quiz submission: code ranks, the summary is written from templates."""

from app.models import db
from app.services.ai_summary import AISummaryGenerator
from app.services.career_data import get_recommendations

ai_summary = AISummaryGenerator()


def submit_quiz(user_id, answers):
    recommendations = get_recommendations(answers)
    summary = ai_summary.generate_quiz_summary(answers, recommendations)
    db.save_quiz_result(user_id, answers, recommendations, summary)

    return {
        'success': True,
        'recommendations': recommendations,
        'summary': summary,
    }
