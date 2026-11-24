"""Code-ranked career recommendations with LLM-written explanations.

The assessment score and profile decide *which* careers appear and in what
order. The language model is called only to replace the short explanation text,
and its reply must be a validated JSON object keyed by the career IDs chosen by
this module. Invalid or missing replies keep the deterministic fallback text.
"""
import json
import math
import re

from app.extensions import sqlalchemy
from app.models import Assessment, AssessmentScore, ChosenCareer, Profile, Recommendation
from app.services import career_data, chatbot_service
from app.services.llm_response import parse_explanation_map

TOP_N = 10
RIASEC_LETTERS = ('R', 'I', 'A', 'S', 'E', 'C')
APTITUDE_KEYS = ('numerical', 'verbal', 'logical', 'spatial')
WEIGHTS = {'riasec': 0.35, 'aptitude': 0.25, 'overlap': 0.20, 'preference': 0.20}

STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'for', 'from',
    'how', 'i', 'in', 'into', 'is', 'it', 'like', 'me', 'my', 'of', 'on',
    'or', 'our', 'that', 'the', 'their', 'this', 'to', 'want', 'what',
    'which', 'with', 'work', 'working', 'you', 'your',
}

RECOMMENDATION_SYSTEM_PROMPT = """You write short, factual career explanations.
Career selection, ranking and scores are computed by application code. Never
invent, reorder or renumber careers, and never include scores or percentages.

Respond with a single valid JSON object and no other text. Use one key per
career ID supplied by the user message, mapped to one short explanation (max
800 characters) describing why that career fits the profile. Do not add keys.
"""


def _as_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    return str(value)


def _tokens(text):
    return {
        word for word in re.findall(r'[a-z]+', _as_text(text).lower())
        if len(word) > 2 and word not in STOPWORDS
    }


def _load_json(value):
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def get_latest_assessment(user_id):
    """Return the newest completed assessment for a user, or None."""
    return Assessment.query.filter_by(
        user_id=user_id, status='completed'
    ).order_by(Assessment.id.desc()).first()


def build_context(user_id):
    """Assemble the code-side inputs for ranking, or None if not assessed."""
    assessment = get_latest_assessment(user_id)
    if assessment is None:
        return None

    score = AssessmentScore.query.filter_by(assessment_id=assessment.id).first()
    profile = Profile.query.filter_by(user_id=user_id).first()
    return {
        'assessment_id': assessment.id,
        'riasec': _load_json(score.riasec_json if score else None),
        'aptitude': _load_json(score.aptitude_json if score else None),
        'prefs': _load_json(score.prefs_json if score else None),
        'stage': profile.stage if profile else None,
        'stream': _as_text(profile.stream if profile else ''),
        'interests_text': _as_text(profile.interests_text if profile else ''),
        'city': _as_text(profile.city if profile else ''),
    }


def _career_text(career):
    return ' '.join(_as_text(career.get(key)) for key in (
        'Career_Name', 'Category', 'Preferred_Stream', 'Required_Degree',
        'Key_Technical_Skills', 'Key_Soft_Skills', 'Job_Outlook',
        'domain', 'work_style', 'key_exams',
    ))


def _stage_allowed(context, career):
    if not context['stage']:
        return True
    stages = set(_as_text(career.get('stages')).split('|'))
    return context['stage'] in stages


def _cosine(user_values, career_values):
    dot = sum(user_values[key] * career_values.get(key, 0.0) for key in user_values)
    user_norm = math.sqrt(sum(value * value for value in user_values.values()))
    career_norm = math.sqrt(sum(value * value for value in career_values.values()))
    if not user_norm or not career_norm:
        return 0.5
    return max(0.0, min(1.0, dot / (user_norm * career_norm)))


def _interest_score(context, career):
    user_tokens = _tokens(context['stream'] + ' ' + context['interests_text'])
    if not user_tokens:
        return 0.5
    career_tokens = _tokens(_career_text(career))
    matched = len(user_tokens & career_tokens)
    return min(1.0, matched / 4.0)


def _preference_score(context, career, max_salary):
    prefs = context['prefs']
    components = []

    salary = career_data.parse_salary(career.get('Entry_Salary_LPA'))
    if salary is not None and max_salary:
        priority = prefs.get('salary_priority', 0.5)
        components.append(max(0.0, min(1.0, salary / max_salary)) * priority + 0.5 * (1 - priority))

    style_text = _tokens(_as_text(career.get('work_style')) + ' ' +
                         _as_text(career.get('Key_Soft_Skills')))
    team_pref = prefs.get('team_style', 0.5)
    if team_pref >= 0.5:
        components.append(1.0 if style_text & {'team', 'service', 'community'} else 0.5)
    else:
        components.append(1.0 if style_text & {'independent', 'analytical', 'field'} else 0.5)

    field_pref = prefs.get('work_setting', 0.5)
    if field_pref >= 0.5:
        components.append(1.0 if style_text & {'field', 'hands', 'active', 'practical'} else 0.5)
    else:
        components.append(1.0 if style_text & {'structured', 'analytical', 'precision'} else 0.5)

    duration = career.get('Duration_Years')
    try:
        years = float(duration)
    except (TypeError, ValueError):
        years = None
    study = prefs.get('study_years', 0.5)
    if years is not None:
        if study <= 0.2:
            components.append(1.0 if years <= 2 else 0.5)
        elif study <= 0.6:
            components.append(1.0 if years <= 4 else 0.5)
        else:
            components.append(1.0 if years >= 5 else 0.5)

    if prefs.get('stability', 0.5) >= 0.5:
        components.append(1.0 if style_text & {'structured', 'precision', 'patient'} else 0.5)

    return sum(components) / len(components) if components else 0.5


def _fallback_explanation(career, breakdown):
    parts = []
    if breakdown['riasec'] >= 0.6:
        parts.append('matches your interest profile')
    if breakdown['aptitude'] >= 0.6:
        parts.append('fits your aptitude strengths')
    if breakdown['overlap'] >= 0.4:
        parts.append('connects with the interests and stream you shared')
    if breakdown['preference'] >= 0.6:
        parts.append('aligns with your work and study preferences')
    if not parts:
        parts.append('is a useful option to explore from your assessment profile')
    return 'This career {}.'.format(', '.join(parts))


def rank(context, top_n=TOP_N):
    """Return code-ranked careers; no language model is involved."""
    careers = career_data.get_all_careers()
    if not careers:
        return []

    salaries = [career_data.parse_salary(c.get('Entry_Salary_LPA')) for c in careers]
    salaries = [value for value in salaries if value is not None]
    max_salary = max(salaries) if salaries else 0

    eligible = [career for career in careers if _stage_allowed(context, career)]
    if not eligible:
        eligible = careers

    ranked = []
    for career in eligible:
        breakdown = {
            'riasec': _cosine(
                {k: float(context['riasec'].get(k) or 0.0) for k in RIASEC_LETTERS},
                {k: float(career.get('riasec_' + k) or 0.0) for k in RIASEC_LETTERS},
            ),
            'aptitude': _cosine(
                {k: float(context['aptitude'].get(k) or 0.0) for k in APTITUDE_KEYS},
                {k: float(career.get('apt_' + k) or 0.0) for k in APTITUDE_KEYS},
            ),
            'overlap': _interest_score(context, career),
            'preference': _preference_score(context, career, max_salary),
        }
        score = round(100 * sum(WEIGHTS[key] * breakdown[key] for key in WEIGHTS), 1)
        career_id = _as_text(career.get('Career_ID'))
        item = dict(career)
        item.update({
            'career_id': career_id,
            'rank': 0,
            'score': score,
            'match_score': score,
            'why_fits': _fallback_explanation(career, breakdown),
        })
        ranked.append((item, breakdown))

    ranked.sort(key=lambda pair: (-pair[0]['score'], pair[0]['career_id']))
    top = []
    for position, (item, breakdown) in enumerate(ranked[:top_n], 1):
        item['rank'] = position
        top.append(item)
    return top


def explain(ranked):
    """Replace fallback explanations with validated LLM text when available."""
    if not ranked:
        return ranked

    keys = [item['career_id'] for item in ranked]
    lines = [
        '{}: {} (code rank {}, code score {})'.format(
            item['career_id'], item.get('Career_Name', ''), item['rank'], item['score']
        )
        for item in ranked
    ]
    prompt = (
        'Write one short explanation for each career below.\n\n'
        + '\n'.join(lines)
        + '\n\nReturn a JSON object keyed by these exact career IDs.'
    )
    raw = chatbot_service.call_groq_completion(
        prompt, RECOMMENDATION_SYSTEM_PROMPT, max_tokens=1200
    )
    explanations = parse_explanation_map(raw, keys)
    if not explanations:
        return ranked

    for item in ranked:
        item['why_fits'] = explanations[item['career_id']]
    return ranked


def save(assessment_id, ranked):
    """Persist the ranked list for one assessment, replacing any earlier run."""
    Recommendation.query.filter_by(assessment_id=assessment_id).delete()
    for item in ranked:
        sqlalchemy.session.add(Recommendation(
            assessment_id=assessment_id,
            career_id=item['career_id'],
            rank=item['rank'],
            score=item['score'],
            why_fits=item['why_fits'],
        ))
    sqlalchemy.session.commit()
    return ranked


def _item_from_row(row):
    career = career_data.get_career(row.career_id)
    if career is None:
        return None
    item = dict(career)
    item.update({
        'career_id': row.career_id,
        'rank': row.rank,
        'score': row.score,
        'match_score': row.score,
        'why_fits': row.why_fits or '',
    })
    return item


def get_recommendations(user_id):
    """Return persisted recommendations, generating them once when needed."""
    context = build_context(user_id)
    if context is None:
        return {'needs_assessment': True, 'items': [], 'chosen': None}

    rows = Recommendation.query.filter_by(
        assessment_id=context['assessment_id']
    ).order_by(Recommendation.rank).all()
    if rows:
        items = [item for item in (_item_from_row(row) for row in rows) if item]
    else:
        ranked = explain(rank(context))
        save(context['assessment_id'], ranked)
        items = ranked

    return {
        'needs_assessment': False,
        'items': items,
        'chosen': get_chosen_career(user_id),
    }


def get_chosen_career(user_id):
    """Return the user's most recently chosen career, if any."""
    row = ChosenCareer.query.filter_by(user_id=user_id).order_by(
        ChosenCareer.id.desc()
    ).first()
    if row is None:
        return None
    chosen = row.to_dict()
    career = career_data.get_career(row.career_id)
    chosen['career_id'] = row.career_id
    chosen['Career_Name'] = career.get('Career_Name') if career else row.career_id
    chosen['Category'] = career.get('Category') if career else ''
    return chosen


def choose_career(user_id, career_id):
    """Store a career the user picked from their recommendations."""
    career_id = _as_text(career_id).strip()
    if not career_id:
        return {'success': False, 'error': 'Please choose a career.'}

    result = get_recommendations(user_id)
    if result['needs_assessment']:
        return {'success': False, 'error': 'Complete the assessment first.'}
    allowed = {item['career_id'] for item in result['items']}
    if career_id not in allowed:
        return {'success': False, 'error': 'Choose a career from your recommendations.'}

    return _store_chosen_career(user_id, career_id)


def choose_career_direct(user_id, career_id):
    """Store a career chosen directly from browsing, with no assessment."""
    career_id = _as_text(career_id).strip()
    if not career_id:
        return {'success': False, 'error': 'Please choose a career.'}
    if career_data.get_career(career_id) is None:
        return {'success': False, 'error': 'That career is not available.'}
    return _store_chosen_career(user_id, career_id)


def _store_chosen_career(user_id, career_id):
    ChosenCareer.query.filter_by(user_id=user_id).delete()
    sqlalchemy.session.add(ChosenCareer(user_id=user_id, career_id=career_id))
    sqlalchemy.session.commit()
    return {'success': True, 'career': get_chosen_career(user_id)}
