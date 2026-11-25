"""Thread-safe contextual session memory store for active voice calls."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sales_agent.intelligence.analyzer import calculate_bant
from sales_agent.utils.pii import redact_pii


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SessionStore:
    """In-memory active call session store (Redis Cluster drop-in for 100k scale)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(
        self,
        language: str = "en",
        prospect_name: str | None = None,
        source: str = "Inbound Voice WebRTC",
    ) -> dict[str, Any]:
        with self._lock:
            sid = f"call-{uuid.uuid4().hex[:8]}"
            now = _utc_now()
            session = {
                "id": sid,
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
                "source": source,
                "language": language,
                "stage": "discovery",
                "profile": {
                    "name": prospect_name,
                    "email": None,
                    "company": None,
                    "role": None,
                    "teamSize": None,
                    "budget": None,
                    "authority": None,
                    "need": None,
                    "timeline": None,
                    "painPoints": [],
                    "objections": [],
                    "appointmentBooked": None,
                },
                "bant": calculate_bant({}),
                "sentimentHistory": [],
                "ragCitations": [],
                "turns": [],
            }
            self._sessions[sid] = session
            return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda s: s["updatedAt"], reverse=True)

    def append_turn(
        self,
        session_id: str,
        *,
        role: str,
        text: str,
        language: str | None = None,
        sentiment: dict[str, Any] | None = None,
        intents: list[str] | None = None,
        rag_hits: list[dict[str, Any]] | None = None,
        latency_ms: int | None = None,
        action: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(f"Session not found: {session_id}")

            turn = {
                "id": len(session["turns"]) + 1,
                "role": role,
                "text": text,
                "redactedText": redact_pii(text),
                "language": language or session["language"],
                "sentiment": sentiment,
                "intents": intents or [],
                "ragHits": rag_hits or [],
                "latencyMs": latency_ms,
                "action": action,
                "timestamp": _utc_now(),
            }
            session["turns"].append(turn)
            session["updatedAt"] = turn["timestamp"]
            if language:
                session["language"] = language

            if role == "user" and sentiment:
                session["sentimentHistory"].append(
                    {
                        "turn": turn["id"],
                        "label": sentiment["label"],
                        "score": sentiment["score"],
                        "timestamp": turn["timestamp"],
                    }
                )

            if rag_hits:
                seen = {c["id"] for c in session["ragCitations"]}
                for hit in rag_hits:
                    if hit["id"] not in seen:
                        seen.add(hit["id"])
                        session["ragCitations"].append(hit)

            return turn

    def update_profile(self, session_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(f"Session not found: {session_id}")

            profile = session["profile"]
            for key, value in updates.items():
                if value is not None:
                    profile[key] = value

            session["bant"] = calculate_bant(profile)
            if profile.get("appointmentBooked"):
                session["stage"] = "booked"
            elif session["bant"]["score"] >= 70:
                session["stage"] = "closing"
            elif session["bant"]["score"] >= 40:
                session["stage"] = "qualification"

            session["updatedAt"] = _utc_now()
            return session

    def close_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(f"Session not found: {session_id}")
            session["status"] = "completed"
            session["updatedAt"] = _utc_now()
            return session
