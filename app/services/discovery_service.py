"""Single 12-question career discovery assessment.

Stored answers and scores reuse the existing assessment tables. The old
three-part assessment service is left untouched for backward compatibility.
"""
import json
from datetime import datetime

from app.extensions import sqlalchemy
from app.models import Assessment, AssessmentAnswer, AssessmentScore
from app.services import profile_service
from data.discovery_questions import (
    APTITUDE_SECTIONS,
    DISCOVERY_QUESTIONS,
    QUESTION_BY_ID,
    RIASEC_LETTERS,
    public_questions,
)

ANSWER_PART = 1
ANSWER_KEY = 'discovery'
PREFERENCE_KEYS = (
    'salary_priority', 'team_style', 'work_setting',
    'location', 'stability', 'study_years',
)
PREFERENCE_DEFAULTS = {
    'salary_priority': 0.6,
    'team_style': 0.5,
    'work_setting': 0.5,
    'location': 0.6,
    'stability': 0.5,
    'study_years': 0.6,
}


def questions():
    return public_questions()


def get_or_create(user_id):
    assessment = Assessment.query.filter_by(
        user_id=user_id, status='in_progress'
    ).order_by(Assessment.id.desc()).first()
    if assessment is None:
        assessment = Assessment(user_id=user_id, status='in_progress', current_part=1)
        sqlalchemy.session.add(assessment)
        sqlalchemy.session.commit()
    return assessment


def get_state(user_id):
    assessment = Assessment.query.filter_by(
        user_id=user_id, status='in_progress'
    ).order_by(Assessment.id.desc()).first()
    if assessment is None:
        assessment = Assessment.query.filter_by(user_id=user_id).order_by(
            Assessment.id.desc()
        ).first()
    if assessment is None:
        return {'assessment_id': None, 'status': None, 'saved': {}}
    return {
        'assessment_id': assessment.id,
        'status': assessment.status,
        'saved': get_answers(assessment.id),
    }


def get_answers(assessment_id):
    row = AssessmentAnswer.query.filter_by(
        assessment_id=assessment_id, part=ANSWER_PART, question_key=ANSWER_KEY
    ).first()
    if row is None or not row.answer_text:
        return {}
    try:
        payload = json.loads(row.answer_text)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def normalise_answers(raw):
    """Validate form data and return (normalised answers, error list)."""
    answers = {}
    errors = []
    for question in questions():
        allowed = {option['value'] for option in question['options']}
        if question['type'] == 'multi':
            values = list(raw.getlist(question['id']))
            values = [value for value in values if value]
            if any(value not in allowed for value in values):
                errors.append('Please choose only the listed options.')
            elif not values:
                errors.append(f"Please answer: {question['text']}")
            elif question.get('max') and len(values) > question['max']:
                errors.append(f"Choose up to {question['max']} options for: {question['text']}")
            answers[question['id']] = values
        else:
            value = (raw.get(question['id']) or '').strip()
            if value not in allowed:
                errors.append(f"Please answer: {question['text']}")
            answers[question['id']] = value
    return answers, list(dict.fromkeys(errors))


def save_answers(user_id, assessment_id, raw):
    """Validate and persist all 12 answers in one JSON blob."""
    assessment = Assessment.query.filter_by(
        id=assessment_id, user_id=user_id, status='in_progress'
    ).first()
    if assessment is None:
        return {'success': False, 'errors': ['This assessment is no longer active.']}

    answers, errors = normalise_answers(raw)
    if errors:
        return {'success': False, 'errors': errors}

    AssessmentAnswer.query.filter_by(
        assessment_id=assessment_id, part=ANSWER_PART, question_key=ANSWER_KEY
    ).delete()
    sqlalchemy.session.add(AssessmentAnswer(
        assessment_id=assessment_id,
        part=ANSWER_PART,
        question_key=ANSWER_KEY,
        answer_text=json.dumps(answers),
    ))
    sqlalchemy.session.commit()
    return {'success': True, 'answers': answers}


def build_score_payload(answers):
    """Map 12 exploratory answers onto the shared recommender score shapes."""
    riasec_counts = {letter: 0 for letter in RIASEC_LETTERS}
    aptitude_counts = {section: 0 for section in APTITUDE_SECTIONS}
    prefs = dict(PREFERENCE_DEFAULTS)
    interest_labels = []

    for question in DISCOVERY_QUESTIONS:
        value = answers.get(question['id'])
        selected = value if isinstance(value, list) else [value]
        for option in question['options']:
            if option['value'] not in selected:
                continue
            for letter in option.get('riasec', {}):
                riasec_counts[letter] += 1
            for section in option.get('aptitude', {}):
                aptitude_counts[section] += 1
            for key, score in option.get('prefs', {}).items():
                prefs[key] = score
            if question.get('profile', {}).get('interests_text'):
                interest_labels.append(option['label'])

    top_count = max(riasec_counts.values()) or 1
    riasec = {
        letter: round(count / top_count, 3)
        for letter, count in riasec_counts.items()
    }
    aptitude = {
        section: round(min(1.0, count / 2.0), 3)
        for section, count in aptitude_counts.items()
    }
    prefs = {key: float(prefs.get(key, 0.5)) for key in PREFERENCE_KEYS}
    top_riasec = sorted(
        RIASEC_LETTERS, key=lambda letter: (-riasec[letter], letter)
    )[:3]

    stage_value = answers.get('d1')
    stage = QUESTION_BY_ID['d1']['profile']['stage'].get(stage_value, 'college')
    return {
        'riasec': riasec,
        'aptitude': aptitude,
        'prefs': prefs,
        'top_riasec': top_riasec,
        'profile': {
            'stage': stage,
            'stream': answers.get('d2') or None,
            'interests_text': ', '.join(interest_labels) or None,
        },
        'riasec_json': json.dumps(riasec),
        'aptitude_json': json.dumps(aptitude),
        'prefs_json': json.dumps(prefs),
    }


def complete(user_id, assessment_id):
    """Finish the assessment, writing scores and a profile when needed."""
    assessment = Assessment.query.filter_by(
        id=assessment_id, user_id=user_id, status='in_progress'
    ).first()
    if assessment is None:
        return {'success': False, 'error': 'This assessment is no longer active.'}

    answers = get_answers(assessment_id)
    if len(answers) != len(DISCOVERY_QUESTIONS):
        return {'success': False, 'error': 'Please answer all 12 questions.'}

    payload = build_score_payload(answers)
    if profile_service.needs_profile(user_id):
        profile_service.save_profile(
            user_id,
            payload['profile']['stage'],
            stream=payload['profile']['stream'],
            interests_text=payload['profile']['interests_text'],
        )

    score = AssessmentScore.query.filter_by(assessment_id=assessment_id).first()
    if score is None:
        score = AssessmentScore(assessment_id=assessment_id)
        sqlalchemy.session.add(score)
    score.riasec_json = payload['riasec_json']
    score.aptitude_json = payload['aptitude_json']
    score.prefs_json = payload['prefs_json']

    assessment.status = 'completed'
    assessment.current_part = 1
    assessment.finished_at = datetime.utcnow()
    sqlalchemy.session.commit()
    return {'success': True, 'payload': payload}
