"""Deterministic, server-side scoring for the combined assessment."""
import json

from data.assessment_questions import (
    APTITUDE_QUESTIONS,
    APTITUDE_SECTIONS,
    INTEREST_STATEMENTS,
    PREFERENCE_QUESTIONS,
    RIASEC_TYPES,
)

PREFERENCE_SCORES = {
    'salary_priority': {'low': 0.2, 'medium': 0.6, 'high': 1.0},
    'team_style': {'team': 1.0, 'solo': 0.0},
    'work_setting': {'desk': 0.0, 'field': 1.0},
    'location': {'city': 0.2, 'town': 0.6, 'remote': 1.0},
    'stability': {'stable': 1.0, 'risk': 0.0},
    'study_years': {'0-2': 0.2, '3-5': 0.6, '6+': 1.0},
}


def _clean_value(value):
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


def score_interests(answers):
    """Average the 1-5 answers for each RIASEC type, normalised to 0-1."""
    buckets = {letter: [] for letter in RIASEC_TYPES}
    for question in INTEREST_STATEMENTS:
        value = _clean_value(answers.get(question['id']))
        if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5:
            buckets[question['type']].append(value)
    return {
        letter: round(sum(values) / len(values) / 5, 3) if values else 0.0
        for letter, values in buckets.items()
    }


def score_aptitude(answers):
    """Grade MCQs against the server-side key; return section scores in 0-1."""
    correct = {section: 0 for section in APTITUDE_SECTIONS}
    total = {section: 0 for section in APTITUDE_SECTIONS}
    for question in APTITUDE_QUESTIONS:
        section = question['section']
        total[section] += 1
        value = _clean_value(answers.get(question['id']))
        if isinstance(value, int) and not isinstance(value, bool) and value == question['correct']:
            correct[section] += 1
    scores = {
        section: round(correct[section] / total[section], 3) if total[section] else 0.0
        for section in APTITUDE_SECTIONS
    }
    scores['correct_count'] = sum(correct.values())
    return scores


def score_preferences(answers):
    """Normalise preference choices into 0-1 weights for the recommender."""
    return {
        question['id']: PREFERENCE_SCORES[question['id']].get(
            _clean_value(answers.get(question['id'])), 0.5
        )
        for question in PREFERENCE_QUESTIONS
    }


def top_riasec(riasec_scores, count=3):
    """Return the highest-scoring RIASEC letters, in descending order."""
    return sorted(RIASEC_TYPES, key=lambda letter: (-riasec_scores[letter], letter))[:count]


def build_score_payload(answers):
    """Combine all three parts into the persisted assessment score payload."""
    riasec = score_interests(answers)
    aptitude = score_aptitude(answers)
    prefs = score_preferences(answers)
    return {
        'riasec': riasec,
        'aptitude': aptitude,
        'prefs': prefs,
        'top_riasec': top_riasec(riasec),
        'riasec_json': json.dumps(riasec),
        'aptitude_json': json.dumps({k: v for k, v in aptitude.items() if k != 'correct_count'}),
        'prefs_json': json.dumps(prefs),
    }
