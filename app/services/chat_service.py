"""Context-aware chatbot orchestration and chat history persistence.

Anonymous visitors keep the original behaviour and may send their own short
history. Logged-in users get history from the database plus their profile,
chosen career and roadmap progress as extra context for the language model.
"""
from app.extensions import sqlalchemy
from app.models import ChosenCareer, ChatMessage, Profile, Roadmap, RoadmapItem
from app.services import career_data, chatbot_service
from app.services.llm_response import parse_explanation

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
        if profile.city:
            lines.append('- City: ' + profile.city)

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
        roadmap = Roadmap.query.filter_by(
            user_id=user_id, career_id=chosen.career_id
        ).order_by(Roadmap.version.desc()).first()
        if roadmap:
            total = RoadmapItem.query.filter_by(roadmap_id=roadmap.id).count()
            done = RoadmapItem.query.filter_by(roadmap_id=roadmap.id, done=True).count()
            if total:
                lines.append('- Roadmap progress: {} of {} steps done'.format(done, total))

    if not lines:
        return ''
    return (
        'Known user context (use it, do not contradict it):\n'
        + '\n'.join(lines)
        + '\nDo not invent scores, rankings or personal details beyond this context.'
    )


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
