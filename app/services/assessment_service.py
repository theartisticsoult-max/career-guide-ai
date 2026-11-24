"""Assessment persistence: start, resume, save each part and finish."""
import json
from datetime import datetime

from data.assessment_questions import APTITUDE_QUESTIONS, INTEREST_STATEMENTS, PREFERENCE_QUESTIONS
from app.extensions import sqlalchemy
from app.models import Assessment, AssessmentAnswer, AssessmentScore
from app.services.scoring import build_score_payload

PART_COUNT = 3


def get_or_create(user_id):
    """Return the user's in-progress assessment, creating one if needed."""
    assessment = Assessment.query.filter_by(user_id=user_id, status='in_progress').first()
    if assessment is None:
        assessment = Assessment(user_id=user_id, status='in_progress', current_part=1)
        sqlalchemy.session.add(assessment)
        sqlalchemy.session.commit()
    return assessment


def get_state(user_id):
    assessment = get_or_create(user_id)
    return {
        'assessment_id': assessment.id,
        'status': assessment.status,
        'current_part': assessment.current_part,
    }


def questions_for_part(part):
    """Return client-safe question data (never includes aptitude answer keys)."""
    if part == 1:
        return [{'id': q['id'], 'text': q['text']} for q in INTEREST_STATEMENTS]
    if part == 2:
        return [
            {'id': q['id'], 'text': q['text'], 'options': q['options']}
            for q in APTITUDE_QUESTIONS
        ]
    if part == 3:
        return PREFERENCE_QUESTIONS
    return []


def get_answers(user_id, assessment_id):
    assessment = Assessment.query.filter_by(id=assessment_id, user_id=user_id).first()
    if assessment is None:
        return {}
    answers = {}
    for row in AssessmentAnswer.query.filter_by(assessment_id=assessment_id).all():
        answers.update(json.loads(row.answer_text or '{}'))
    return answers


def save_part(user_id, assessment_id, part, answers):
    """Persist one part and advance the progress pointer."""
    assessment = Assessment.query.filter_by(id=assessment_id, user_id=user_id).first()
    if assessment is None or part < 1 or part > PART_COUNT:
        return None

    for row in AssessmentAnswer.query.filter_by(assessment_id=assessment_id, part=part).all():
        sqlalchemy.session.delete(row)
    sqlalchemy.session.add(AssessmentAnswer(
        assessment_id=assessment_id,
        part=part,
        question_key='part-' + str(part),
        answer_text=json.dumps(answers or {}),
    ))
    assessment.current_part = min(part + 1, PART_COUNT)
    sqlalchemy.session.commit()
    return get_state(user_id)


def complete(user_id, assessment_id, answers):
    """Score the combined answers server-side and mark the assessment done."""
    assessment = Assessment.query.filter_by(id=assessment_id, user_id=user_id).first()
    if assessment is None:
        return None

    payload = build_score_payload(answers)
    existing = AssessmentScore.query.filter_by(assessment_id=assessment_id).first()
    if existing is None:
        existing = AssessmentScore(assessment_id=assessment_id)
        sqlalchemy.session.add(existing)
    existing.riasec_json = payload['riasec_json']
    existing.aptitude_json = payload['aptitude_json']
    existing.prefs_json = payload['prefs_json']
    assessment.status = 'completed'
    assessment.current_part = PART_COUNT
    assessment.finished_at = datetime.utcnow()
    sqlalchemy.session.commit()
    return payload
