"""SQLite-backed CRM, Calendar Booking, Webhook Outbox, and Business Insights Store."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class CRMStore:
    """Thread-safe SQLite repository for CRM leads, appointments, summaries, and webhook outbox."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._seed_if_empty()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    session_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT,
                    company TEXT NOT NULL,
                    role TEXT,
                    team_size INTEGER,
                    budget TEXT,
                    authority TEXT,
                    need TEXT,
                    timeline TEXT,
                    bant_score INTEGER NOT NULL,
                    tier TEXT NOT NULL,
                    language TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS appointments (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    lead_id TEXT,
                    prospect_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    company TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    day_label TEXT NOT NULL,
                    time TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    status TEXT NOT NULL,
                    meeting_link TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(date, time, status)
                );

                CREATE TABLE IF NOT EXISTS call_summaries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT UNIQUE NOT NULL,
                    lead_id TEXT NOT NULL,
                    prospect_name TEXT NOT NULL,
                    company TEXT NOT NULL,
                    language TEXT NOT NULL,
                    bant_score INTEGER NOT NULL,
                    tier TEXT NOT NULL,
                    avg_sentiment REAL NOT NULL,
                    sentiment_label TEXT NOT NULL,
                    objections_json TEXT NOT NULL,
                    rag_citations_json TEXT NOT NULL,
                    appointment_booked INTEGER NOT NULL,
                    appointment_json TEXT,
                    executive_summary TEXT NOT NULL,
                    next_best_action TEXT NOT NULL,
                    follow_up_email TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS webhook_outbox (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def _seed_if_empty(self) -> None:
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            if count > 0:
                return

            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO leads (id, session_id, name, email, company, role, team_size, budget, authority, need, timeline, bant_score, tier, language, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "lead-seed-01", "call-seed-01", "Aarav Mehta", "aarav.mehta@finserve.io",
                        "FinServe Corp", "VP of Sales", 45, "$899/month (Growth)",
                        "Decision Maker (VP of Sales)", "Slow lead response / missed follow-ups",
                        "this month", 95, "Hot", "en", "Demo Booked", yesterday,
                    ),
                )
                self._conn.execute(
                    """
                    INSERT INTO leads (id, session_id, name, email, company, role, team_size, budget, authority, need, timeline, bant_score, tier, language, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "lead-seed-02", "call-seed-02", "Elena Gomez", "elena@solaris.es",
                        "Solaris Energy", "Sales Manager", 18, None,
                        "Decision Maker (Sales Manager)", "Multilingual coverage gaps",
                        "next quarter", 58, "Warm", "es", "Qualified - Follow-up", yesterday,
                    ),
                )

                self._conn.execute(
                    """
                    INSERT INTO call_summaries (id, session_id, lead_id, prospect_name, company, language, bant_score, tier, avg_sentiment, sentiment_label, objections_json, rag_citations_json, appointment_booked, appointment_json, executive_summary, next_best_action, follow_up_email, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "sum-seed-01", "call-seed-01", "lead-seed-01", "Aarav Mehta", "FinServe Corp", "en",
                        95, "Hot", 0.65, "Positive", json.dumps(["Security & Compliance Verification"]),
                        json.dumps([]), 1, None,
                        "Aarav Mehta (VP of Sales, FinServe Corp, 45 reps) inquired about reducing lead response latency. Confirmed Growth plan fit ($899/mo), verified SOC 2 Type II encryption, and booked a live product demo.",
                        "Send SOC 2 attestation brief and calendar invite before demo.",
                        "Hi Aarav, thanks for speaking with NexaCloud AI! Attached is our SOC 2 Type II summary ahead of your NexaOps Growth demo.",
                        yesterday,
                    ),
                )
                self._conn.execute(
                    """
                    INSERT INTO call_summaries (id, session_id, lead_id, prospect_name, company, language, bant_score, tier, avg_sentiment, sentiment_label, objections_json, rag_citations_json, appointment_booked, appointment_json, executive_summary, next_best_action, follow_up_email, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "sum-seed-02", "call-seed-02", "lead-seed-02", "Elena Gomez", "Solaris Energy", "es",
                        58, "Warm", 0.2, "Neutral", json.dumps(["Price / Budget Concern"]),
                        json.dumps([]), 0, None,
                        "Elena Gomez evaluated Spanish voice automation for 18 reps targeting next quarter. Requested ROI proof before budget approval.",
                        "Share FinServe 6-week payback case study and 14-day PoV pilot offer.",
                        "Hola Elena, gracias por tu tiempo. Te comparto el caso de éxito con retorno en 6 semanas y nuestra prueba piloto de 14 días.",
                        yesterday,
                    ),
                )

    def get_available_slots(self, days_ahead: int = 3) -> list[dict[str, str]]:
        """Generate open business-day slots excluding already-confirmed appointments."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT date, time FROM appointments WHERE status != 'cancelled'"
            ).fetchall()
            booked_keys = {(r["date"], r["time"]) for r in rows}

        slots: list[dict[str, str]] = []
        times = ["10:00 AM", "02:00 PM", "04:30 PM"]
        cursor = datetime.now(timezone.utc)
        added_days = 0

        while added_days < days_ahead:
            cursor += timedelta(days=1)
            if cursor.weekday() >= 5:  # Skip Saturday/Sunday
                continue
            date_str = cursor.strftime("%Y-%m-%d")
            day_label = cursor.strftime("%a, %b %d")
            for t in times:
                if (date_str, t) not in booked_keys:
                    slots.append(
                        {
                            "slotId": f"{date_str}_{t.replace(' ', '')}",
                            "date": date_str,
                            "dayLabel": day_label,
                            "time": t,
                            "timezone": "IST / Local",
                        }
                    )
            added_days += 1
        return slots

    def book_appointment(
        self,
        *,
        session_id: str,
        lead_id: str | None = None,
        prospect_name: str | None = None,
        email: str | None = None,
        company: str | None = None,
        slot_id: str | None = None,
        date: str | None = None,
        time: str | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Atomically book an open demo slot with conflict detection and CRM webhook emission."""
        with self._lock:
            available = self.get_available_slots(5)
            chosen = None
            if slot_id:
                chosen = next((s for s in available if s["slotId"] == slot_id), None)
            elif date and time:
                chosen = next((s for s in available if s["date"] == date and s["time"].lower() == time.lower()), None)
            elif available:
                chosen = available[0]

            if not chosen:
                return {
                    "ok": False,
                    "error": "Requested slot is unavailable or already booked.",
                    "availableSlots": available[:3],
                }

            appointment = {
                "id": f"apt-{uuid.uuid4().hex[:8]}",
                "sessionId": session_id,
                "leadId": lead_id,
                "prospectName": prospect_name or "Valued Prospect",
                "email": email or "pending@prospect.com",
                "company": company or "Unspecified Company",
                "slotId": chosen["slotId"],
                "date": chosen["date"],
                "dayLabel": chosen["dayLabel"],
                "time": chosen["time"],
                "timezone": chosen["timezone"],
                "status": "confirmed",
                "meetingLink": f"https://meet.nexacloud.ai/{uuid.uuid4().hex[:8]}",
                "notes": notes,
                "createdAt": _utc_now(),
            }

            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO appointments (id, session_id, lead_id, prospect_name, email, company, slot_id, date, day_label, time, timezone, status, meeting_link, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        appointment["id"], appointment["sessionId"], appointment["leadId"],
                        appointment["prospectName"], appointment["email"], appointment["company"],
                        appointment["slotId"], appointment["date"], appointment["dayLabel"],
                        appointment["time"], appointment["timezone"], appointment["status"],
                        appointment["meetingLink"], appointment["notes"], appointment["createdAt"],
                    ),
                )
                self._emit_webhook_locked("calendar.appointment.booked", appointment)
            return {"ok": True, "appointment": appointment}

    def upsert_lead_from_session(self, session: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            p = session["profile"]
            bant = session["bant"]
            status = (
                "Demo Booked"
                if p.get("appointmentBooked")
                else "SQL - Ready to Close"
                if bant["tier"] == "Hot"
                else "MQL - Nurturing"
                if bant["tier"] == "Warm"
                else "New Lead"
            )

            existing = self._conn.execute(
                "SELECT id FROM leads WHERE session_id = ?", (session["id"],)
            ).fetchone()
            lead_id = existing["id"] if existing else f"lead-{uuid.uuid4().hex[:8]}"
            now = _utc_now()

            record = {
                "id": lead_id,
                "sessionId": session["id"],
                "name": p.get("name") or "Anonymous Prospect",
                "email": p.get("email"),
                "company": p.get("company") or "Unknown Company",
                "role": p.get("role"),
                "teamSize": p.get("teamSize"),
                "budget": p.get("budget"),
                "authority": p.get("authority"),
                "need": p.get("need"),
                "timeline": p.get("timeline"),
                "bantScore": bant["score"],
                "tier": bant["tier"],
                "language": session["language"],
                "status": status,
                "updatedAt": now,
            }

            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO leads (id, session_id, name, email, company, role, team_size, budget, authority, need, timeline, bant_score, tier, language, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        name=excluded.name, email=excluded.email, company=excluded.company,
                        role=excluded.role, team_size=excluded.team_size, budget=excluded.budget,
                        authority=excluded.authority, need=excluded.need, timeline=excluded.timeline,
                        bant_score=excluded.bant_score, tier=excluded.tier, language=excluded.language,
                        status=excluded.status, updated_at=excluded.updated_at
                    """,
                    (
                        record["id"], record["sessionId"], record["name"], record["email"],
                        record["company"], record["role"], record["teamSize"], record["budget"],
                        record["authority"], record["need"], record["timeline"], record["bantScore"],
                        record["tier"], record["language"], record["status"], record["updatedAt"],
                    ),
                )
                self._emit_webhook_locked("crm.lead.upserted", record)
            return record

    def save_call_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO call_summaries (id, session_id, lead_id, prospect_name, company, language, bant_score, tier, avg_sentiment, sentiment_label, objections_json, rag_citations_json, appointment_booked, appointment_json, executive_summary, next_best_action, follow_up_email, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    bant_score=excluded.bant_score, tier=excluded.tier, avg_sentiment=excluded.avg_sentiment,
                    sentiment_label=excluded.sentiment_label, objections_json=excluded.objections_json,
                    rag_citations_json=excluded.rag_citations_json, appointment_booked=excluded.appointment_booked,
                    appointment_json=excluded.appointment_json, executive_summary=excluded.executive_summary,
                    next_best_action=excluded.next_best_action, follow_up_email=excluded.follow_up_email
                """,
                (
                    summary["id"], summary["sessionId"], summary["leadId"], summary["prospectName"],
                    summary["company"], summary["language"], summary["bantScore"], summary["tier"],
                    summary["avgSentiment"], summary["sentimentLabel"],
                    json.dumps(summary.get("objections", [])),
                    json.dumps(summary.get("ragCitations", [])),
                    1 if summary.get("appointmentBooked") else 0,
                    json.dumps(summary.get("appointment")) if summary.get("appointment") else None,
                    summary["executiveSummary"], summary["nextBestAction"], summary["followUpEmail"],
                    summary["createdAt"],
                ),
            )
            self._emit_webhook_locked("crm.call.summarized", summary)
        return summary

    def _emit_webhook_locked(self, event_type: str, payload: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO webhook_outbox (id, provider, event_type, status, timestamp, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"wh-{uuid.uuid4().hex[:8]}",
                "HubSpot/Salesforce Adapter",
                event_type,
                "delivered_simulated",
                _utc_now(),
                json.dumps(payload),
            ),
        )
        self._conn.execute(
            """
            DELETE FROM webhook_outbox WHERE id NOT IN (
                SELECT id FROM webhook_outbox ORDER BY timestamp DESC LIMIT 40
            )
            """
        )

    def get_all_data(self) -> dict[str, Any]:
        with self._lock:
            leads = [
                {
                    "id": r["id"], "sessionId": r["session_id"], "name": r["name"], "email": r["email"],
                    "company": r["company"], "role": r["role"], "teamSize": r["team_size"],
                    "budget": r["budget"], "authority": r["authority"], "need": r["need"],
                    "timeline": r["timeline"], "bantScore": r["bant_score"], "tier": r["tier"],
                    "language": r["language"], "status": r["status"], "updatedAt": r["updated_at"],
                }
                for r in self._conn.execute("SELECT * FROM leads ORDER BY updated_at DESC").fetchall()
            ]
            appointments = [
                {
                    "id": r["id"], "sessionId": r["session_id"], "leadId": r["lead_id"],
                    "prospectName": r["prospect_name"], "email": r["email"], "company": r["company"],
                    "slotId": r["slot_id"], "date": r["date"], "dayLabel": r["day_label"],
                    "time": r["time"], "timezone": r["timezone"], "status": r["status"],
                    "meetingLink": r["meeting_link"], "notes": r["notes"], "createdAt": r["created_at"],
                }
                for r in self._conn.execute("SELECT * FROM appointments ORDER BY created_at DESC").fetchall()
            ]
            summaries = [
                {
                    "id": r["id"], "sessionId": r["session_id"], "leadId": r["lead_id"],
                    "prospectName": r["prospect_name"], "company": r["company"], "language": r["language"],
                    "bantScore": r["bant_score"], "tier": r["tier"], "avgSentiment": r["avg_sentiment"],
                    "sentimentLabel": r["sentiment_label"],
                    "objections": json.loads(r["objections_json"]),
                    "ragCitations": json.loads(r["rag_citations_json"]),
                    "appointmentBooked": bool(r["appointment_booked"]),
                    "appointment": json.loads(r["appointment_json"]) if r["appointment_json"] else None,
                    "executiveSummary": r["executive_summary"],
                    "nextBestAction": r["next_best_action"],
                    "followUpEmail": r["follow_up_email"],
                    "createdAt": r["created_at"],
                }
                for r in self._conn.execute("SELECT * FROM call_summaries ORDER BY created_at DESC").fetchall()
            ]
            webhooks = [
                {
                    "id": r["id"], "provider": r["provider"], "eventType": r["event_type"],
                    "status": r["status"], "timestamp": r["timestamp"],
                    "payload": json.loads(r["payload_json"]),
                }
                for r in self._conn.execute("SELECT * FROM webhook_outbox ORDER BY timestamp DESC LIMIT 30").fetchall()
            ]
            return {
                "leads": leads,
                "appointments": appointments,
                "callSummaries": summaries,
                "webhookOutbox": webhooks,
                "availableSlots": self.get_available_slots(3),
                "insights": self._compute_insights(leads, summaries),
            }

    @staticmethod
    def _compute_insights(leads: list[dict[str, Any]], summaries: list[dict[str, Any]]) -> dict[str, Any]:
        total_leads = len(leads)
        hot_leads = sum(1 for l in leads if l["tier"] == "Hot")
        warm_leads = sum(1 for l in leads if l["tier"] == "Warm")
        booked_count = sum(1 for l in leads if l["status"] == "Demo Booked")
        avg_bant = round(sum(l["bantScore"] for l in leads) / total_leads) if total_leads else 0

        obj_counts: dict[str, int] = {}
        lang_counts: dict[str, int] = {}
        for s in summaries:
            for obj in s.get("objections", []):
                obj_counts[obj] = obj_counts.get(obj, 0) + 1
        for l in leads:
            lang = l.get("language") or "en"
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        top_objections = sorted(
            [{"name": k, "count": v} for k, v in obj_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        return {
            "totalLeads": total_leads,
            "hotLeads": hot_leads,
            "warmLeads": warm_leads,
            "bookedCount": booked_count,
            "qualificationRate": round(((hot_leads + warm_leads) / total_leads) * 100) if total_leads else 0,
            "bookingConversionRate": round((booked_count / total_leads) * 100) if total_leads else 0,
            "avgBantScore": avg_bant,
            "avgSentiment": round(sum(s["avgSentiment"] for s in summaries) / len(summaries), 2) if summaries else 0,
            "topObjections": top_objections,
            "languageDistribution": lang_counts,
        }
