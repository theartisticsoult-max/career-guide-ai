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
