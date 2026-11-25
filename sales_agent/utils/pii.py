"""PII redaction utility for compliance-safe audit logging (SOC 2 / GDPR / DPDP)."""

from __future__ import annotations

import re

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b")


def redact_pii(text: str) -> str:
    """Mask sensitive SSNs, payment cards, emails, and phone numbers in text."""
    if not isinstance(text, str) or not text:
        return text
    masked = _SSN_RE.sub("[REDACTED_SSN]", text)
    masked = _CARD_RE.sub("[REDACTED_CARD]", masked)
    masked = _EMAIL_RE.sub(r"\1***\2", masked)
    return _PHONE_RE.sub(
        lambda m: "[REDACTED_PHONE]" if sum(ch.isdigit() for ch in m.group(0)) >= 10 else m.group(0),
        masked,
    )
