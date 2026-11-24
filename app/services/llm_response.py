"""Validation for LLM-written explanations and roadmaps.

Ranking and scoring are done in Python; the model is only allowed to write
explanatory text. Structured replies are accepted as validated JSON, and
anything unusable falls back to the non-LLM knowledge base.
"""
import json

ANSWER_KEYS = ('answer', 'response', 'explanation', 'roadmap')


def parse_explanation(raw):
    """Return an explanation string from an LLM completion, or None.

    Expected JSON shape: {"answer": "<markdown explanation or roadmap>"}
    Plain-text completions are accepted for compatibility with older clients;
    malformed JSON objects are rejected so callers use their fallback.
    """
    if not raw or not isinstance(raw, str):
        return None

    text = raw.strip()
    if not text:
        return None

    if text.startswith('```'):
        text = text.strip('`').strip()
        if text.lower().startswith('json'):
            text = text[4:].strip()

    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        # A JSON-shaped reply that does not parse is unusable: let the caller
        # fall back. Bare text from older clients stays compatible.
        if text[0] in '{[':
            return None
        return text

    if not isinstance(payload, dict):
        return None

    for key in ANSWER_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def parse_explanation_map(raw, keys, max_length=800):
    """Return validated ``{key: explanation}`` JSON, or None.

    ``keys`` are supplied by application code (the already-ranked career IDs).
    The model cannot add, remove or reorder careers; it may only replace the
    explanation text. Any missing, empty or oversized value falls back.
    """
    if not raw or not isinstance(raw, str) or not keys:
        return None

    text = raw.strip()
    if text.startswith('```'):
        text = text.strip('`').strip()
        if text.lower().startswith('json'):
            text = text[4:].strip()

    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None

    result = {}
    for key in keys:
        value = payload.get(key)
        if not isinstance(value, str):
            return None
        value = value.strip()
        if not value or len(value) > max_length:
            return None
        result[key] = value
    return result


ROADMAP_ITEM_TYPES = {'skill', 'course', 'project', 'certification', 'exam'}


def parse_roadmap(raw, max_items=12):
    """Return validated roadmap items, or None so callers use their fallback.

    Expected JSON shape: ``{"roadmap": [ ... ]}`` or a bare list. Every item
    must supply a phase, an allowed type, a title and a detail string.
    """
    if not raw or not isinstance(raw, str):
        return None

    text = raw.strip()
    if text.startswith('```'):
        text = text.strip('`').strip()
        if text.lower().startswith('json'):
            text = text[4:].strip()

    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return None

    if isinstance(payload, dict):
        items = payload.get('roadmap')
    elif isinstance(payload, list):
        items = payload
    else:
        return None

    if not isinstance(items, list) or not 3 <= len(items) <= max_items:
        return None

    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            return None
        item_type = item.get('type')
        phase = item.get('phase')
        title = item.get('title')
        detail = item.get('detail')
        weeks = item.get('est_weeks', 0)
        if item_type not in ROADMAP_ITEM_TYPES:
            return None
        if not isinstance(phase, str) or not phase.strip() or len(phase) > 80:
            return None
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            return None
        if not isinstance(detail, str) or not detail.strip() or len(detail) > 1000:
            return None
        if isinstance(weeks, bool) or not isinstance(weeks, int) or not 0 <= weeks <= 52:
            return None
        cleaned.append({
            'phase': phase.strip(),
            'type': item_type,
            'title': title.strip(),
            'detail': detail.strip(),
            'est_weeks': weeks,
        })
    return cleaned
