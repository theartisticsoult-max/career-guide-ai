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

ROADMAP_SYSTEM_PROMPT = """You write practical career roadmaps for students and career changers.
Use only the career facts supplied by the application. Do not name specific
courses, institutes, certifications, employers or qualifications. Do not invent
salaries, rankings, admission guarantees or other statistics. Cover short and
long milestones and use weekly or monthly phases where helpful.

Respond with a single valid JSON object and no other text:
{"roadmap": [{"phase": "Weeks 1-2", "type": "skill|course|project|certification|exam", "title": "...", "detail": "...", "est_weeks": 4}]}
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
    degree = _as_text(career.get('Required_Degree')) or 'the relevant qualification'
    exams = _as_text(career.get('Entrance_Exams')) or 'the relevant entry route'
    duration = _as_text(career.get('Duration_Years')) or '3-4'
    pathway = _as_text(career.get('pathway')) or (
        'Study the fundamentals, build skills, gain practical experience, then apply.'
    )
    licensing = _as_text(career.get('licensing_note')) or (
        'Verify local rules before committing to this path.'
    )
    first_skill = skills[0] if skills else 'the core fundamentals of this field'
    skill_text = ', '.join(skills[:4]) if skills else first_skill
    soft_text = ', '.join(soft_skills[:3]) if soft_skills else 'communication and teamwork'

    return [
        {
            'phase': 'Weeks 1-2 · short milestone',
            'type': 'skill',
            'title': 'Understand this career path',
            'detail': (
                f'Read the {name} overview, compare it with your interests, and note the '
                f'usual route: {pathway}.'
            ),
            'est_weeks': 2,
        },
        {
            'phase': 'Weeks 3-4 · short milestone',
            'type': 'course',
            'title': 'Check qualifications and eligibility',
            'detail': (
                f'Review the expected qualification ({degree}), entry route ({exams}), '
                f'and typical study time (about {duration} years). {licensing}'
            ),
            'est_weeks': 2,
        },
        {
            'phase': 'Month 1 · short milestone',
            'type': 'skill',
            'title': 'Build core skills with free resources',
            'detail': (
                f'Start with {skill_text}. Use the Learning Resources page, official '
                'syllabuses or trusted open material; develop ' + soft_text + ' alongside.'
            ),
            'est_weeks': 4,
        },
        {
            'phase': 'Month 2 · short milestone',
            'type': 'project',
            'title': 'Create one portfolio project',
            'detail': (
                f'Apply {first_skill} in a small piece of work and add it to a simple '
                'portfolio. Write a short note explaining the problem, your steps and '
                'what you learned.'
            ),
            'est_weeks': 4,
        },
        {
            'phase': 'Month 3 · short milestone',
            'type': 'project',
            'title': 'Gain practical experience',
            'detail': (
                'Look for an internship, volunteer role, job shadow or local practical '
                'experience related to this field. Keep a record of tasks and outcomes.'
            ),
            'est_weeks': 4,
        },
        {
            'phase': 'Months 4-6 · long milestone',
            'type': 'certification',
            'title': 'Prepare for entry and interview',
            'detail': (
                'Choose a recognised short course or certification only after checking local '
                'requirements. Update your resume with skills and projects, then practise '
                'simple interview answers and apply for suitable entry roles.'
            ),
            'est_weeks': 12,
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
        'Soft skills: ' + _as_text(career.get('Key_Soft_Skills')) + '\n'
        'Duration in years: ' + _as_text(career.get('Duration_Years')) + '\n'
        'Pathway: ' + _as_text(career.get('pathway')) + '\n'
        'Licensing note: ' + _as_text(career.get('licensing_note')) + '\n'
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
    career = career_data.get_career(career_id) or {}
    roadmap = Roadmap.query.filter_by(
        user_id=user_id, career_id=career_id
    ).order_by(Roadmap.version.desc()).first()

    if roadmap is None:
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
    next_milestone = next((item for item in items if not item['done']), None)
    return {
        'needs_career': False,
        'roadmap_id': roadmap.id,
        'career': {**career, **chosen},
        'skills': _split_list(career.get('Key_Technical_Skills')) +
                  _split_list(career.get('Key_Soft_Skills')),
        'items': items,
        'next_milestone': next_milestone,
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
