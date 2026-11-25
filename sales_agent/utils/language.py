"""Multilingual detection and BCP-47 speech metadata."""

from __future__ import annotations

import re

SUPPORTED_LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"code": "en", "bcp47": "en-US", "label": "English"},
    "hi": {"code": "hi", "bcp47": "hi-IN", "label": "Hindi"},
    "es": {"code": "es", "bcp47": "es-ES", "label": "Spanish"},
    "fr": {"code": "fr", "bcp47": "fr-FR", "label": "French"},
    "de": {"code": "de", "bcp47": "de-DE", "label": "German"},
}

_EXPLICIT_SWITCH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("hi", re.compile(r"\b(hindi|हिंदी|हिन्दी|hinglish)\b", re.IGNORECASE)),
    ("es", re.compile(r"\b(spanish|español|espanol)\b", re.IGNORECASE)),
    ("fr", re.compile(r"\b(french|français|francais)\b", re.IGNORECASE)),
    ("de", re.compile(r"\b(german|deutsch)\b", re.IGNORECASE)),
    ("en", re.compile(r"\b(english|inglés|anglais)\b", re.IGNORECASE)),
]

_SWITCH_CONTEXT_RE = re.compile(
    r"\b(speak|talk|switch|in|bol|baat|habla|parle|sprich|language|hindi|español|français|deutsch)\b",
    re.IGNORECASE,
)

_KEYWORD_SIGNALS: dict[str, set[str]] = {
    "hi": {
        "namaste", "kya", "kaise", "kitna", "paisa", "paise", "haan", "nahi",
        "chahiye", "batao", "samay", "karna", "humara", "mera", "aapka", "mein",
    },
    "es": {
        "hola", "gracias", "precio", "cuánto", "cuanto", "necesito", "empresa",
        "reunión", "reunion", "sí", "buenos", "días", "demo", "quiero", "podemos",
    },
    "fr": {
        "bonjour", "merci", "prix", "combien", "besoin", "entreprise",
        "réunion", "reunion", "oui", "pouvez", "voudrais", "sécurité",
    },
    "de": {
        "hallo", "danke", "preis", "kosten", "unternehmen", "termin",
        "brauchen", "sicherheit", "können", "möchte",
    },
}


def detect_language(text: str, current_lang: str = "en") -> str:
    """Detect language from text using explicit switch intent, scripts, and keyword signals."""
    if not text or not text.strip():
        return current_lang

    if _SWITCH_CONTEXT_RE.search(text):
        for lang, pattern in _EXPLICIT_SWITCH_PATTERNS:
            if pattern.search(text):
                return lang

    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    if re.search(r"[¿¡ñ]", text, re.IGNORECASE):
        return "es"
    if re.search(r"[çœàâêîôûéè]", text, re.IGNORECASE) and not re.search(r"\b(resume|cafe|naive)\b", text, re.IGNORECASE):
        return "fr"
    if re.search(r"[äöüß]", text, re.IGNORECASE):
        return "de"

    tokens = re.findall(r"[^\W_]+", text.lower())
    best_lang = current_lang
    best_hits = 0

    for lang, keywords in _KEYWORD_SIGNALS.items():
        hits = sum(1 for tok in tokens if tok in keywords)
        if (hits >= 2 or (hits == 1 and len(tokens) <= 4)) and hits > best_hits:
            best_hits = hits
            best_lang = lang

    return best_lang


def get_language_meta(code: str) -> dict[str, str]:
    """Return language metadata including BCP-47 locale tag."""
    return SUPPORTED_LANGUAGES.get(code, SUPPORTED_LANGUAGES["en"])
