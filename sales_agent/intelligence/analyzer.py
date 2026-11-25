"""Real-time BANT lead qualification, entity extraction, intent & sentiment analyzer."""

from __future__ import annotations

import re
from typing import Any

_POSITIVE_WORDS = (
    "great", "awesome", "love", "interested", "helpful", "perfect", "sounds good",
    "yes", "sure", "definitely", "excited", "fast", "good", "impressed", "book", "schedule",
    "excellent", "gracias", "genial", "merci", "parfait", "accha", "badiya", "haan",
)

_NEGATIVE_WORDS = (
    "expensive", "too much", "costly", "hate", "frustrated", "annoying", "waste",
    "not interested", "no budget", "worried", "concern", "skeptical", "doubt",
    "competitor", "cancel", "stop", "bad", "hard", "complicated", "mahanga", "nahi", "caro",
)

_PAIN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Slow lead response / missed follow-ups", re.compile(r"\b(slow|missed|hours|latency|follow[- ]?up|delay|leak|drop)\b", re.I)),
    ("Manual CRM data entry", re.compile(r"\b(manual|crm|data entry|admin|copy[- ]?paste|spreadsheet|hubspot|salesforce)\b", re.I)),
    ("Scaling outbound / rep bandwidth", re.compile(r"\b(scale|scaling|bandwidth|overload|volume|reps|team|too many leads)\b", re.I)),
    ("Multilingual coverage gaps", re.compile(r"\b(language|multilingual|hindi|spanish|global|region|accent)\b", re.I)),
]

_EXCLUDED_COMPANIES = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Google", "Salesforce", "HubSpot"}


def analyze_turn(text: str, existing_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Analyze a prospect utterance for sentiment, intents, objections, and BANT updates."""
    existing_profile = existing_profile or {}
    lower = (text or "").lower()

    # 1. Sentiment scoring (-1.0 to +1.0)
    pos_hits = sum(1 for w in _POSITIVE_WORDS if w in lower)
    neg_hits = sum(1 for w in _NEGATIVE_WORDS if w in lower)

    sentiment_score = 0.05
    if pos_hits > 0 or neg_hits > 0:
        sentiment_score = (pos_hits - neg_hits * 1.1) / max(1, pos_hits + neg_hits)
    sentiment_score = round(max(-1.0, min(1.0, sentiment_score)), 2)

    sentiment_label = "Neutral"
    if sentiment_score >= 0.3:
        sentiment_label = "Positive"
    elif sentiment_score <= -0.35:
        sentiment_label = "Frustrated"
    elif sentiment_score < 0 or re.search(r"\b(but|however|worried|concern|expensive|security|why)\b", lower):
        sentiment_label = "Skeptical"

    # 2. Intent & objection detection
    intents: list[str] = []
    objections: list[str] = []

    if re.search(r"\b(hello|hi|hey|namaste|hola|bonjour|hallo|good morning|good afternoon)\b", lower):
        intents.append("greeting")
    if re.search(r"\b(price|pricing|cost|tier|plan|budget|discount|kitna|precio|prix|kosten)\b", lower):
        intents.append("pricing_inquiry")
    if re.search(r"\b(security|soc2|gdpr|privacy|encrypt|hipaa|compliance|pii)\b", lower):
        intents.append("security_check")
    if re.search(r"\b(salesforce|hubspot|zoho|crm|calendar|outlook|google|integrate|integration|api)\b", lower):
        intents.append("integration_inquiry")
    if re.search(r"\b(book|schedule|demo|meeting|call|slot|tomorrow|tuesday|wednesday|thursday|friday|calendar|appointment)\b", lower):
        intents.append("booking_intent")
    if re.search(r"\b(roi|case study|results|payback|savings|worth)\b", lower):
        intents.append("roi_inquiry")
    if re.search(r"\b(setup|onboard|timeline|how long|deploy|migrate)\b", lower):
        intents.append("onboarding_inquiry")

    if re.search(r"\b(expensive|too much|costly|over budget|no budget|cheaper|mahanga|caro)\b", lower):
        objections.append("Price / Budget Concern")
    if re.search(r"\b(security|privacy|gdpr|compliance|leak|trust|safe)\b", lower):
        objections.append("Security & Compliance Verification")
    if re.search(r"\b(not sure|already have|competitor|chatbot|dialer|status quo)\b", lower):
        objections.append("Existing Tool / Competitor Comparison")
    if re.search(r"\b(long|complex|hard to setup|it team|migration)\b", lower):
        objections.append("Implementation Effort Concern")

    # 3. Entity & BANT extraction
    updates: dict[str, Any] = {}

    name_match = re.search(r"\b(?:i am|i'm|my name is|this is|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text, re.I)
    if name_match and not re.search(r"interested|looking|calling|from", name_match.group(1), re.I):
        updates["name"] = name_match.group(1).strip()

    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    if email_match:
        updates["email"] = email_match.group(0)

    company_match = re.search(
        r"\b(?:from|at|with|company is|work at|represent)\s+([A-Z][A-Za-z0-9&-]+(?:\s+[A-Z][A-Za-z0-9&-]+)?)(?=[.,!?\s]|$)",
        text,
    )
    if company_match and company_match.group(1) not in _EXCLUDED_COMPANIES:
        updates["company"] = company_match.group(1).strip()

    role_match = re.search(
        r"\b(VP|Vice President|Head of Sales|Director|CTO|CEO|Founder|Sales Manager|RevOps|Operations Manager|SDR Manager|Manager)\b",
        text,
        re.I,
    )
    if role_match:
        role = role_match.group(1)
        updates["role"] = role
        is_dm = bool(re.search(r"vp|vice president|head|director|cto|ceo|founder|manager", role, re.I))
        updates["authority"] = f"{'Decision Maker' if is_dm else 'Influencer'} ({role})"
    elif re.search(r"\b(i decide|my team|decision maker|approve|sign off)\b", lower):
        updates["authority"] = "Confirmed Decision Maker"

    team_match = re.search(r"\b(\d{1,4})\s*(?:sales\s*)?(?:reps|agents|seats|users|people|members)\b", text, re.I)
    if team_match:
        updates["teamSize"] = int(team_match.group(1))

    budget_match = re.search(r"(\$\s?\d[\d,]*(?:\s*[kKmM])?(?:\s*(?:/|\s*per\s*)(?:mo|month|yr|year))?)", text)
    if budget_match:
        updates["budget"] = re.sub(r"\s+", " ", budget_match.group(1)).strip()
    elif re.search(r"\b(growth plan|starter plan|enterprise plan|\$899|\$299|\$2,?400)\b", lower):
        updates["budget"] = re.search(r"\b(growth|starter|enterprise|\$\d[\d,]*)\b", text, re.I).group(0)
    elif re.search(r"\b(budget approved|have budget|allocated budget|within budget)\b", lower):
        updates["budget"] = "Approved / Active Budget"

    timeline_match = re.search(
        r"\b(this week|next week|this month|next month|this quarter|q[1-4]|immediately|asap|urgent|within \d+ (?:days|weeks|months))\b",
        text,
        re.I,
    )
    if timeline_match:
        updates["timeline"] = timeline_match.group(1)

    detected_pains = [label for label, pattern in _PAIN_PATTERNS if pattern.search(text)]
    if detected_pains:
        merged_pains = list(dict.fromkeys([*(existing_profile.get("painPoints") or []), *detected_pains]))
        updates["painPoints"] = merged_pains
        updates["need"] = "; ".join(merged_pains)

    if objections:
        updates["objections"] = list(dict.fromkeys([*(existing_profile.get("objections") or []), *objections]))

    return {
        "sentiment": {"label": sentiment_label, "score": sentiment_score},
        "intents": intents or ["general_conversation"],
        "objections": objections,
        "updates": updates,
    }


def calculate_bant(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute BANT score (0-100), Hot/Warm/Cold tier, and missing qualification dimensions."""
    profile = profile or {}
    breakdown = {
        "budget": 25 if profile.get("budget") else 0,
        "authority": 25 if profile.get("authority") else 0,
        "need": 25 if (profile.get("need") or profile.get("painPoints")) else 0,
        "timeline": 25 if profile.get("timeline") else 0,
    }

    bonus = 0
    if (profile.get("teamSize") or 0) >= 10:
        bonus += 5
    if profile.get("company"):
        bonus += 3
    if profile.get("appointmentBooked"):
        bonus += 10

    score = min(100, sum(breakdown.values()) + bonus)
    tier = "Hot" if score >= 70 else "Warm" if score >= 40 else "Cold"

    missing = []
    if not breakdown["need"]:
        missing.append("Need / Pain Point")
    if not breakdown["authority"]:
        missing.append("Decision Authority")
    if not breakdown["timeline"]:
        missing.append("Implementation Timeline")
    if not breakdown["budget"]:
        missing.append("Budget Range")

    return {"score": score, "tier": tier, "breakdown": breakdown, "missing": missing}
