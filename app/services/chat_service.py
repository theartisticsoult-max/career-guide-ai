"""Context-aware AI Career Mentor orchestration and chat history persistence.

Anonymous visitors keep the original behaviour and may send their own short
history. Logged-in users get history from the database plus their profile,
discovery answers, recommendations, chosen career and roadmap progress.
"""
import json

from app.extensions import sqlalchemy
from app.models import (
    Assessment, AssessmentAnswer, ChosenCareer, ChatMessage, Profile,
    Recommendation, Roadmap, RoadmapItem,
)
from app.services import career_data, chatbot_service
from app.services.llm_response import parse_explanation, parse_mentor_answer
from data.discovery_questions import DISCOVERY_QUESTIONS

PROMPT_HISTORY_LIMIT = 8
DISPLAY_HISTORY_LIMIT = 20


def _sanitised_turns(history):
    turns = []
    if not isinstance(history, list):
        return turns
    for turn in history[-PROMPT_HISTORY_LIMIT:]:
        if not isinstance(turn, dict):
            continue
        role = turn.get('role')
        content = turn.get('content')
        if role in ('user', 'assistant') and isinstance(content, str) and content.strip():
            turns.append({'role': role, 'content': content.strip()})
    return turns


def get_prompt_history(user_id):
    """Return the last turns in chronological order for the LLM payload."""
    if not user_id:
        return []
    rows = ChatMessage.query.filter_by(user_id=user_id).order_by(
        ChatMessage.id.desc()
    ).limit(PROMPT_HISTORY_LIMIT).all()
    return [
        {'role': row.role, 'content': row.message}
        for row in reversed(rows)
        if row.role in ('user', 'assistant') and row.message
    ]


def get_display_history(user_id):
    """Return recent messages for the chat screen."""
    if not user_id:
        return []
    rows = ChatMessage.query.filter_by(user_id=user_id).order_by(
        ChatMessage.id.desc()
    ).limit(DISPLAY_HISTORY_LIMIT).all()
    return [row.to_dict() for row in reversed(rows)]


def clear_history(user_id):
    """Remove all stored messages for one user."""
    if not user_id:
        return 0
    deleted = ChatMessage.query.filter_by(user_id=user_id).delete()
    sqlalchemy.session.commit()
    return deleted


RIASEC_NAMES = {
    'R': 'building and practical work',
    'I': 'investigating and problem solving',
    'A': 'creative work',
    'S': 'helping and teaching',
    'E': 'leading and persuading',
    'C': 'organising and working with data',
}
CONTEXT_QUESTION_IDS = ('d1', 'd2', 'd3', 'd4', 'd6', 'd10', 'd12')


def _load_json(text):
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _discovery_answer_lines(assessment_id):
    row = AssessmentAnswer.query.filter_by(
        assessment_id=assessment_id, question_key='discovery'
    ).first()
    if row is None:
        return []
    answers = _load_json(row.answer_text)
    if not answers:
        return []
    questions = {question['id']: question for question in DISCOVERY_QUESTIONS}
    labels = []
    for question_id in CONTEXT_QUESTION_IDS:
        question = questions.get(question_id)
        value = answers.get(question_id)
        if not question or not value:
            continue
        selected = value if isinstance(value, list) else [value]
        option_labels = [
            option['label'] for option in question['options']
            if option['value'] in selected
        ]
        if option_labels:
            labels.append('; '.join(option_labels))
    return ['- Discovery answers: ' + ' | '.join(labels)] if labels else []


def _assessment_context(user_id):
    assessment = Assessment.query.filter_by(
        user_id=user_id, status='completed'
    ).order_by(Assessment.id.desc()).first()
    if assessment is None:
        return []

    lines = _discovery_answer_lines(assessment.id)
    score = assessment.score
    if score is not None:
        riasec = _load_json(score.riasec_json)
        top = sorted(
            riasec.items(), key=lambda pair: (-_number(pair[1]), pair[0])
        )[:2]
        top = [letter for letter, value in top if _number(value) > 0]
        if top:
            lines.append(
                '- Interest themes from discovery: ' + ', '.join(
                    RIASEC_NAMES.get(letter, letter) for letter in top
                )
            )

    suggestions = []
    for row in Recommendation.query.filter_by(
        assessment_id=assessment.id
    ).order_by(Recommendation.rank).limit(3).all():
        career = career_data.get_career(row.career_id) or {}
        name = career.get('Career_Name') or row.career_id
        category = career.get('Category') or ''
        suggestions.append('{} ({})'.format(name, category).rstrip(' ()'))
    if suggestions:
        lines.append('- Careers to explore from discovery: ' + '; '.join(suggestions))
    return lines


def build_context(user_id):
    """Build a short, factual context block from the user's saved data."""
    if not user_id:
        return ''

    lines = []
    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile:
        if profile.stage:
            lines.append('- Stage: ' + profile.stage)
        if profile.stream:
            lines.append('- Stream: ' + profile.stream)
        if profile.interests_text:
            lines.append('- Interests: ' + profile.interests_text)
            lines.append('- Learning goals stated: ' + profile.interests_text)
        if profile.city:
            lines.append('- City: ' + profile.city)
        if profile.country:
            lines.append('- Country: ' + profile.country)
        if profile.region:
            lines.append('- State/region: ' + profile.region)

    lines.extend(_assessment_context(user_id))

    chosen = ChosenCareer.query.filter_by(user_id=user_id).order_by(
        ChosenCareer.id.desc()
    ).first()
    if chosen:
        career = career_data.get_career(chosen.career_id) or {}
        lines.append(
            '- Chosen career: {} ({})'.format(
                career.get('Career_Name', chosen.career_id),
                career.get('Category', ''),
            ).rstrip(' ()')
        )
        skills = [
            value.strip()
            for value in (
                str(career.get('Key_Technical_Skills') or '').split(',') +
                str(career.get('Key_Soft_Skills') or '').split(',')
            )
            if value.strip()
        ]
        if skills:
            lines.append('- Skills linked to this career: ' + ', '.join(skills[:6]))

        roadmap = Roadmap.query.filter_by(
            user_id=user_id, career_id=chosen.career_id
        ).order_by(Roadmap.version.desc()).first()
        if roadmap:
            total = RoadmapItem.query.filter_by(roadmap_id=roadmap.id).count()
            done = RoadmapItem.query.filter_by(roadmap_id=roadmap.id, done=True).count()
            if total:
                lines.append('- Roadmap progress: {} of {} steps done'.format(done, total))
            completed = RoadmapItem.query.filter_by(
                roadmap_id=roadmap.id, done=True
            ).order_by(RoadmapItem.id).limit(3).all()
            if completed:
                lines.append('- Completed milestones: ' + '; '.join(
                    item.title for item in completed
                ))
            pending = RoadmapItem.query.filter_by(
                roadmap_id=roadmap.id, done=False
            ).order_by(RoadmapItem.id).first()
            if pending:
                lines.append('- Next milestone: ' + pending.title)

    if not lines:
        return ''
    return (
        'Known user context (use it, do not contradict it):\n'
        + '\n'.join(lines)
        + '\nDo not invent scores, rankings or personal details beyond this context.'
    )


def mentor_fallback(message, context):
    """Structured, non-LLM answer for logged-in mentor requests."""
    facts = [
        line[2:].strip() for line in (context or '').splitlines()
        if line.startswith('- ')
    ]
    known = [fact for fact in facts if not fact.startswith('Do not invent')]

    def find(prefix):
        return next((fact for fact in known if fact.startswith(prefix)), None)

    chosen = find('Chosen career:')
    next_step = find('Next milestone:')
    suggestions = find('Careers to explore from discovery:')
    stage = find('Stage:')
    country = find('Country:')

    lines = ['**What I know**']
    if known:
        lines.extend('- ' + fact for fact in known[:6])
    else:
        lines.append('- I do not have your education, interests or location yet.')

    lines.append('')
    lines.append('**Practical next steps**')
    if chosen:
        lines.append('1. Stay with ' + chosen + ' for now and review its qualification and skill requirements.')
    elif suggestions:
        lines.append('1. Compare ' + suggestions + ' before choosing one path.')
    else:
        lines.append('1. Tell me your education stage, stream and location so I can narrow this down.')
    if next_step:
        lines.append('2. Work on your next roadmap milestone: ' + next_step + '.')
    else:
        lines.append('2. Pick one career, then build a short roadmap from its skills and entry route.')
    if country:
        lines.append('3. Check local rules and entry requirements for ' + country + ' before committing.')
    else:
        lines.append('3. Check local rules and entry requirements before committing.')

    lines.append('')
    lines.append('**Clarifying question**')
    if stage:
        lines.append('Which part do you want help with next: qualifications, skills, projects or applications?')
    else:
        lines.append('What is your current education stage, and which career are you considering?')
    return '\n'.join(lines)


def respond(user_id, message, client_history=None):
    """Generate a response and persist it for logged-in users."""
    message = (message or '').strip()
    if not message:
        return ''

    logged_in = bool(user_id)
    history = get_prompt_history(user_id) if logged_in else _sanitised_turns(client_history)
    context = build_context(user_id) if logged_in else ''
    system_prompt = chatbot_service.SYSTEM_PROMPT
    if context:
        system_prompt += '\n\n' + context

    raw = chatbot_service.call_groq_completion(message, system_prompt, history)
    if logged_in:
        explanation = parse_mentor_answer(raw)
        response = explanation or mentor_fallback(message, context)
    else:
        explanation = parse_explanation(raw)
        response = explanation or chatbot_service.get_intelligent_fallback_response(
            message, career_data.career_df
        )

    if logged_in:
        sqlalchemy.session.add(ChatMessage(
            user_id=user_id, role='user', message=message
        ))
        sqlalchemy.session.add(ChatMessage(
            user_id=user_id, role='assistant', message=response
        ))
        sqlalchemy.session.commit()
    return response
