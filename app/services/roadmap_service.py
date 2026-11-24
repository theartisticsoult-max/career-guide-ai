"""Personal roadmap generation and progress tracking.

The language model may write roadmap text, but only as validated JSON. If it is
unavailable or returns anything invalid, a deterministic roadmap built from the
career catalogue is used instead.
"""
import math
from datetime import datetime

from app.extensions import sqlalchemy
from app.models import Roadmap, RoadmapItem
from app.services import career_data, chatbot_service, recommendation_service
from app.services.llm_response import parse_roadmap

ROADMAP_SYSTEM_PROMPT = """You write practical career roadmaps for students.
Use only the career facts supplied by the application. Do not invent salaries,
rankings or admission guarantees.

Respond with a single valid JSON object and no other text:
{"roadmap": [{"phase": "...", "type": "skill|course|project|certification|exam", "title": "...", "detail": "...", "est_weeks": 4}]}
Return 3-12 items. Use only the listed types. Keep each detail under 1000 characters.
"""


def _as_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    return str(value)


def _split_list(value):
    return [part.strip() for part in _as_text(value).split(',') if part.strip()]


def build_fallback(career):
    """Build a deterministic roadmap from catalogue fields."""
    name = _as_text(career.get('Career_Name')) or 'this career'
    skills = _split_list(career.get('Key_Technical_Skills'))
    soft_skills = _split_list(career.get('Key_Soft_Skills'))
    degree = _as_text(career.get('Required_Degree')) or 'a relevant degree'
    exams = _as_text(career.get('Entrance_Exams')) or 'the relevant admission process'
    duration = _as_text(career.get('Duration_Years')) or '3-4'
    first_skill = skills[0] if skills else 'the core fundamentals of this field'

    return [
        {
            'phase': 'Phase 1: Foundations',
            'type': 'skill',
            'title': 'Understand the career path',
            'detail': f'Learn what {name} professionals do day to day and which subjects matter most.',
            'est_weeks': 2,
        },
        {
            'phase': 'Phase 1: Foundations',
            'type': 'course',
            'title': 'Study the required fundamentals',
            'detail': f'Build the foundation expected for {degree}. This path usually takes about {duration} years of formal study.',
            'est_weeks': 8,
        },
        {
            'phase': 'Phase 2: Core Skills',
            'type': 'skill',
            'title': 'Practise key technical skills',
            'detail': 'Focus on ' + (', '.join(skills[:4]) if skills else first_skill) + '.',
            'est_weeks': 12,
        },
        {
            'phase': 'Phase 2: Core Skills',
            'type': 'project',
            'title': 'Create a portfolio project',
            'detail': f'Apply {first_skill} in a small project you can show to mentors or employers.',
            'est_weeks': 8,
        },
        {
            'phase': 'Phase 3: Preparation',
            'type': 'exam',
            'title': 'Prepare for entry requirements',
            'detail': f'Research {exams} and plan the eligibility steps for {name}.',
            'est_weeks': 6,
        },
        {
            'phase': 'Phase 3: Preparation',
            'type': 'certification',
            'title': 'Strengthen your profile',
            'detail': 'Earn a recognised certification or short course, and develop ' +
                      (', '.join(soft_skills[:2]) if soft_skills else 'communication and teamwork') + '.',
            'est_weeks': 6,
        },
    ]


def generate_items(career):
    """Try the LLM for wording, then validate; otherwise use fallback items."""
    fallback = build_fallback(career)
    prompt = (
        'Create a step-by-step roadmap for this career.\n'
        'Career: ' + _as_text(career.get('Career_Name')) + '\n'
        'Category: ' + _as_text(career.get('Category')) + '\n'
        'Education: ' + _as_text(career.get('Required_Degree')) + '\n'
        'Entrance or entry route: ' + _as_text(career.get('Entrance_Exams')) + '\n'
        'Key skills: ' + _as_text(career.get('Key_Technical_Skills')) + '\n'
        'Duration in years: ' + _as_text(career.get('Duration_Years')) + '\n'
    )
    raw = chatbot_service.call_groq_completion(
        prompt, ROADMAP_SYSTEM_PROMPT, max_tokens=1800
    )
    return parse_roadmap(raw) or fallback


def _item_dict(item):
    data = item.to_dict()
    data['done'] = bool(data['done'])
    return data


def get_roadmap(user_id):
    """Return the chosen career's roadmap, generating it once if needed."""
    chosen = recommendation_service.get_chosen_career(user_id)
    if chosen is None:
        return {'needs_career': True, 'items': [], 'progress': 0}

    career_id = chosen['career_id']
    roadmap = Roadmap.query.filter_by(
        user_id=user_id, career_id=career_id
    ).order_by(Roadmap.version.desc()).first()

    if roadmap is None:
        career = career_data.get_career(career_id) or {}
        roadmap = Roadmap(user_id=user_id, career_id=career_id, version=1)
        sqlalchemy.session.add(roadmap)
        sqlalchemy.session.flush()
        for item in generate_items(career):
            sqlalchemy.session.add(RoadmapItem(roadmap_id=roadmap.id, **item))
        sqlalchemy.session.commit()

    items = [_item_dict(item) for item in RoadmapItem.query.filter_by(
        roadmap_id=roadmap.id
    ).order_by(RoadmapItem.id).all()]
    done = sum(1 for item in items if item['done'])
    progress = round(done / len(items) * 100) if items else 0
    return {
        'needs_career': False,
        'roadmap_id': roadmap.id,
        'career': chosen,
        'items': items,
        'done_count': done,
        'progress': progress,
    }


def toggle_item(user_id, item_id):
    """Mark one roadmap item done or not done, if it belongs to the user."""
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return {'success': False, 'error': 'Invalid roadmap item.'}

    item = RoadmapItem.query.join(Roadmap).filter(
        RoadmapItem.id == item_id,
        Roadmap.user_id == user_id,
    ).first()
    if item is None:
        return {'success': False, 'error': 'Roadmap item not found.'}

    item.done = not item.done
    item.done_at = datetime.utcnow() if item.done else None
    sqlalchemy.session.commit()
    return {'success': True, 'done': item.done}
