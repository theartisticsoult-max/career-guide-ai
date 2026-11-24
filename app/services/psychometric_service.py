"""Psychometric submission: code ranks, the report is written from templates."""

from app import db
from app.services.ai_summary import AISummaryGenerator
from app.services.psychometric import get_career_matches_from_psychometric

ai_summary = AISummaryGenerator()


def submit_psychometric(user_id, data):
    personality = data.get('personality', {})
    interests = data.get('interests', {})
    aptitudes = data.get('aptitudes', {})
    work_styles = data.get('workStyles', {})
    # The client sends 'value_data'; older payloads used 'values'.
    value_data = data.get('value_data', {})
    raw_answers = data.get('raw_answers', {})

    career_matches = get_career_matches_from_psychometric(data)
    summary = ai_summary.generate_psychometric_summary(
        personality, interests, aptitudes, work_styles, value_data, career_matches
    )

    db.save_psychometric_result(
        user_id,
        personality,
        interests,
        aptitudes,
        work_styles,
        value_data,
        raw_answers,
        summary,
        career_matches,
    )

    return {
        'success': True,
        'personality': personality,
        'interests': interests,
        'aptitudes': aptitudes,
        'workStyles': work_styles,
        'value_data': value_data,
        'career_matches': career_matches,
        'summary': summary,
    }
