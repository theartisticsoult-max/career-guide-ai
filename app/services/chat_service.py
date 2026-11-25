"""Context-aware AI Career Mentor orchestration and chat history persistence.

Anonymous visitors keep the original behaviour and may send their own short
history. Logged-in users get history from the database plus their profile,
discovery answers, recommendations, chosen career and roadmap progress.
"""
import json
import re

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

FOLLOWUP_INTENTS = {
    'skills': {
        'skill', 'skills', 'what skills', 'skills please',
        'tell me skills', 'tell me about skills',
    },
    'projects': {
        'project', 'projects', 'what projects', 'projects please',
        'tell me projects', 'tell me about projects',
    },
    'qualifications': {
        'qualification', 'qualifications', 'what qualifications',
        'qualifications please', 'tell me qualifications',
        'tell me about qualifications',
    },
    'applications': {
        'application', 'applications', 'what applications',
        'applications please', 'tell me applications',
        'tell me about applications',
    },
}
FOLLOWUP_FILLERS = {'about', 'for', 'me', 'my', 'only', 'please', 'the', 'this', 'what'}


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


def detect_followup_intent(message, history=None):
    """Return the topic selected by a short follow-up, or None.

    A answer such as "skills" is handled in code so provider failure or a weak
    LLM answer cannot turn it back into the same clarification question.
    """
    text = (message or '').strip().lower()
    text = re.sub(
        r"^(?:i want|i need|i would like|i'd like|tell me about|tell me|give me|show me)\s+",
        '', text,
    )
    text = re.sub(r'[\s.!?]+$', '', text)

    for intent, aliases in FOLLOWUP_INTENTS.items():
        if text in aliases:
            return intent

    words = text.split()
    if not words or len(words) > 4:
        return None
    for intent, aliases in FOLLOWUP_INTENTS.items():
        if any(word in aliases for word in words) and all(
            word in aliases or word in FOLLOWUP_FILLERS for word in words
        ):
            # A previous clarification is not required: the short topic is
            # unambiguous on its own. It is accepted here for context checks.
            if history is None or any(
                isinstance(turn, dict) and turn.get('role') == 'assistant'
                for turn in history
            ):
                return intent
    return None


def _career_for_mentor(user_id):
    """Return the selected career, or the top discovery suggestion."""
    if not user_id:
        return {}
    chosen = ChosenCareer.query.filter_by(user_id=user_id).order_by(
        ChosenCareer.id.desc()
    ).first()
    if chosen:
        return career_data.get_career(chosen.career_id) or {}

    assessment = Assessment.query.filter_by(
        user_id=user_id, status='completed'
    ).order_by(Assessment.id.desc()).first()
    if assessment is not None:
        row = Recommendation.query.filter_by(
            assessment_id=assessment.id
        ).order_by(Recommendation.rank).first()
        if row is not None:
            return career_data.get_career(row.career_id) or {}
    return {}


def _context_facts(context):
    return [
        line[2:].strip() for line in (context or '').splitlines()
        if line.startswith('- ')
    ]


def _fact(facts, prefix):
    return next(
        (fact[len(prefix):].strip() for fact in facts if fact.startswith(prefix)),
        '',
    )


def _clean(value):
    text = str(value or '').strip()
    if not text or text.lower() in {'varies', 'not specified', 'none', 'nan'}:
        return ''
    return text


def _career_label(career, facts):
    name = _clean(career.get('Career_Name'))
    if name:
        return name
    chosen = _fact(facts, 'Chosen career:')
    if chosen:
        return chosen.split(' (')[0]
    suggestions = _fact(facts, 'Careers to explore from discovery:')
    if suggestions:
        return suggestions.split(';')[0].split(' (')[0]
    return ''


def _career_skills(career, facts):
    skills = []
    values = (
        career.get('Key_Technical_Skills'),
        career.get('Key_Soft_Skills'),
        _fact(facts, 'Skills linked to this career:'),
    )
    for value in values:
        for part in str(value or '').split(','):
            skill = _clean(part)
            if skill and skill not in skills:
                skills.append(skill)
    return skills[:8]


def _location(facts):
    parts = (
        _fact(facts, 'City:'),
        _fact(facts, 'State/region:'),
        _fact(facts, 'Country:'),
    )
    return ', '.join(part for part in parts if part)


def _skills_answer(label, skills, interests, location):
    title = '**Skills to learn next**'
    if label:
        title += ' for **' + label + '**'
    lines = [title, '', '**Practical learning order**']
    lines.extend([
        '1. **Communication and problem-solving** — explain a problem clearly, ask useful questions and break it into smaller steps.',
        '2. **Business fundamentals and financial literacy** — understand costs, pricing, basic records and how decisions affect results.',
        '3. **Leadership** — practice planning, giving feedback and following through on a small responsibility.',
        '4. **Marketing** — learn to describe value simply, choose one audience and check whether the message lands.',
    ])
    if skills:
        lines.append('')
        lines.append('Career-linked skills from your saved path: ' + ', '.join(skills[:6]) + '.')
    if interests:
        lines.append('This connects to your stated interest in ' + interests + '.')
    lines.extend([
        '',
        '**Beginner-friendly exercise**',
        'Write one page about a real problem you noticed: who has it, what you would measure, and how you would explain the solution in five sentences.',
    ])
    if location:
        lines.append('Check current expectations in ' + location + ' before choosing any course or certification.')
    return '\n'.join(lines)


def _projects_answer(label, skills, next_step):
    lines = ['**Beginner-friendly projects**', '']
    if label:
        lines.append('These suit **' + label + '** and can be done without a formal role.')
    lines.extend([
        '1. **Small business plan** — teaches business fundamentals, goal setting and basic finance.',
        '2. **Customer survey** — teaches communication, asking useful questions and problem-solving.',
        '3. **Simple budget spreadsheet** — teaches financial literacy and tracking assumptions.',
        '4. **Marketing campaign** — teaches messaging, leadership and measuring response.',
    ])
    if skills:
        lines.append('')
        lines.append('Link each project back to your saved skills: ' + ', '.join(skills[:6]) + '.')
    if next_step:
        lines.append('Do the project that best supports your next roadmap milestone: ' + next_step + '.')
    lines.append('Start with the customer survey if you want the quickest first win.')
    return '\n'.join(lines)


def _qualifications_answer(label, career, stage, location):
    lines = ['**Educational pathway and requirements**', '']
    if label:
        lines.append('For **' + label + '**, the saved career data says:')
    degree = _clean(career.get('Required_Degree'))
    minimum = _clean(career.get('Min_Education'))
    stream = _clean(career.get('Preferred_Stream'))
    exams = _clean(career.get('Entrance_Exams'))
    duration = _clean(career.get('Duration_Years'))
    pathway = _clean(career.get('pathway'))
    licensing = _clean(career.get('licensing_note'))

    lines.append('- Required degree: ' + degree + '.' if degree else
                 '- No fixed degree is listed; verify current rules.')
    if minimum:
        lines.append('- Minimum education listed: ' + minimum + '.')
    if stream:
        lines.append('- Preferred stream: ' + stream + '.')
    lines.append('- Entrance exams: ' + exams + '.' if exams else
                 '- No fixed entrance exam is listed; verify current rules.')
    if duration:
        lines.append('- Duration listed: ' + duration + ' years.')
    if pathway:
        lines.append('- Typical pathway: ' + pathway + '.')
    if licensing:
        lines.append('- Local check: ' + licensing)
    if stage:
        lines.append('You are currently at **' + stage + '**; compare this route with your stream before committing.')
    if location:
        lines.append('Check current rules in ' + location + ' before choosing an exam or course.')
    if not label:
        lines.append('Choose a career from Discover Careers or complete discovery for a more specific requirement list.')
    return '\n'.join(lines)


def _applications_answer(label, career, skills, next_step, location):
    lines = ['**Practical opportunities and how to prepare**', '']
    if label:
        lines.append('For **' + label + '**, treat applications as real entry routes, not just forms.')
    category = str(career.get('Category') or '').lower()
    if 'management' in category or 'business' in category:
        lines.append('1. Try a small service: write a one-page offer, interview one potential customer and record what you learned.')
    elif 'health' in category or 'law' in category or 'government' in category:
        lines.append('1. Seek a beginner volunteer, assistant or observership task and keep a short record of what you did.')
    elif 'art' in category or 'design' in category or 'media' in category:
        lines.append('1. Create one small portfolio piece, ask for feedback and revise it once.')
    elif 'education' in category:
        lines.append('1. Plan a short teaching or tutoring session and note what helped the learner.')
    elif 'trade' in category or 'skilled' in category:
        lines.append('1. Assist on a safe beginner task and practice the basic steps repeatedly.')
    else:
        lines.append('1. Find a beginner internship, volunteer task or small project related to the career and complete one concrete deliverable.')

    lines.append('2. Prepare a one-page resume around that deliverable and practice a two-minute explanation of what you did and learned.')
    if skills:
        lines.append('3. Show evidence of these saved skills: ' + ', '.join(skills[:6]) + '.')
    else:
        lines.append('3. Add one skill at a time as you complete each small task.')
    if next_step:
        lines.append('Your next roadmap milestone is ' + next_step + '; complete it first if it is still open.')
    licensing = _clean(career.get('licensing_note'))
    if licensing:
        lines.append('Local check: ' + licensing)
    if location:
        lines.append('Verify current entry rules in ' + location + ' before applying.')
    return '\n'.join(lines)


def followup_answer(message, context, user_id=None, history=None):
    """Return a deterministic answer for a short follow-up topic, or None."""
    intent = detect_followup_intent(message, history)
    if not intent:
        return None

    facts = _context_facts(context)
    career = _career_for_mentor(user_id)
    label = _career_label(career, facts)
    skills = _career_skills(career, facts)
    location = _location(facts)
    stage = _fact(facts, 'Stage:')
    interests = _fact(facts, 'Interests:')
    next_step = _fact(facts, 'Next milestone:')

    if intent == 'skills':
        return _skills_answer(label, skills, interests, location)
    if intent == 'projects':
        return _projects_answer(label, skills, next_step)
    if intent == 'qualifications':
        return _qualifications_answer(label, career, stage, location)
    return _applications_answer(label, career, skills, next_step, location)


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

    followup = followup_answer(message, context, user_id, history)
    if followup:
        response = followup
    else:
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
