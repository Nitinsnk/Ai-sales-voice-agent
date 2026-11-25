"""Autonomous AI Sales Voice Agent orchestrator (Python)."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from sales_agent.crm.crm_store import CRMStore
from sales_agent.intelligence.analyzer import analyze_turn
from sales_agent.memory.session_store import SessionStore
from sales_agent.rag.retriever import HybridRetriever
from sales_agent.utils.language import detect_language, get_language_meta

LOCALIZED_PHRASES: dict[str, dict[str, Any]] = {
    "en": {
        "greeting": "Hello! I'm Aria, the AI Sales Advisor at NexaCloud AI. How is your sales team handling inbound lead follow-ups today?",
        "empathyPrefix": "I completely understand that concern.",
        "bookedConfirm": lambda apt: (
            f"Awesome—I've confirmed your live demo for {apt['dayLabel']} at {apt['time']} ({apt['timezone']}) "
            "and synced the invite to our CRM. Anything else you'd like to verify before we wrap up?"
        ),
        "offerSlot": lambda slots: (
            f"Would you like me to lock in a quick 20-minute demo? I have openings on "
            f"{slots[0]['dayLabel']} at {slots[0]['time']} or "
            f"{(slots[1] if len(slots) > 1 else slots[0])['dayLabel']} at {(slots[1] if len(slots) > 1 else {'time': '02:00 PM'})['time']}."
        ),
        "askNeed": "To tailor this for your team, what is your biggest bottleneck right now—response speed, CRM manual updates, or rep capacity?",
        "askTeamTimeline": "Roughly how many sales reps are on your team, and are you looking to roll this out this month or next quarter?",
        "askAuthorityBudget": "Are you evaluating this for your own team, and do you have a target monthly budget range in mind?",
        "askEmail": "What email address should I send the calendar invite and summary to?",
        "fallbackInfo": "NexaOps automates instant AI voice qualification, RAG-grounded Q&A, and one-click CRM calendar booking in under 500 milliseconds.",
    },
    "hi": {
        "greeting": "नमस्ते! मैं NexaCloud AI से Aria बोल रही हूँ। आपकी सेल्स टीम अभी इनबाउंड लीड्स और फॉलो-अप कैसे मैनेज कर रही है?",
        "empathyPrefix": "मैं आपकी चिंता पूरी तरह समझती हूँ।",
        "bookedConfirm": lambda apt: (
            f"बढ़िया! मैंने आपका लाइव डेमो {apt['dayLabel']} को {apt['time']} पर कन्फर्म कर दिया है और CRM में सेव कर दिया है। क्या आप कुछ और जानना चाहेंगे?"
        ),
        "offerSlot": lambda slots: (
            f"क्या मैं आपके लिए 20 मिनट का लाइव डेमो बुक कर दूँ? मेरे पास {slots[0]['dayLabel']} को {slots[0]['time']} का स्लॉट खाली है।"
        ),
        "askNeed": "आपकी टीम के लिए सबसे बड़ी चुनौती क्या है—लीड रिस्पॉन्स टाइम, मैनुअल CRM एंट्री, या टीम की क्षमता?",
        "askTeamTimeline": "आपकी सेल्स टीम में कितने लोग हैं और आप इसे कब तक शुरू करना चाहते हैं?",
        "askAuthorityBudget": "क्या आप अपनी टीम के लिए निर्णय ले रहे हैं और आपका अनुमानित मासिक बजट क्या है?",
        "askEmail": "मैं कैलेंडर इनवाइट किस ईमेल पते पर भेजूं?",
        "fallbackInfo": "NexaOps 500ms से कम लेटेंसी के साथ हिंदी और अंग्रेजी में AI वॉयस क्वालिफिकेशन, RAG आधारित जवाब और ऑटोमैटिक CRM बुकिंग देता है।",
    },
    "es": {
        "greeting": "¡Hola! Soy Aria, asesora de ventas de NexaCloud AI. ¿Cómo maneja su equipo el seguimiento de leads hoy?",
        "empathyPrefix": "Entiendo perfectamente esa preocupación.",
        "bookedConfirm": lambda apt: f"¡Perfecto! Confirmé su demo para el {apt['dayLabel']} a las {apt['time']} y lo sincronicé con nuestro CRM.",
        "offerSlot": lambda slots: f"¿Le gustaría agendar una demo de 20 minutos? Tengo disponibilidad el {slots[0]['dayLabel']} a las {slots[0]['time']}.",
        "askNeed": "¿Cuál es su principal reto hoy: velocidad de respuesta, registro manual en CRM o capacidad del equipo?",
        "askTeamTimeline": "¿Cuántos representantes hay en su equipo y para cuándo planean implementarlo?",
        "askAuthorityBudget": "¿Evalúa esta solución para su equipo y manejan un presupuesto mensual estimado?",
        "askEmail": "¿A qué correo electrónico le envío la invitación de calendario?",
        "fallbackInfo": "NexaOps automatiza llamadas de calificación con voz en tiempo real, respuestas verificadas con RAG y reserva directa en CRM.",
    },
    "fr": {
        "greeting": "Bonjour ! Je suis Aria de NexaCloud AI. Comment votre équipe commerciale gère-t-elle le suivi des prospects ?",
        "empathyPrefix": "Je comprends tout à fait cette préoccupation.",
        "bookedConfirm": lambda apt: f"Parfait ! Votre démo est confirmée pour le {apt['dayLabel']} à {apt['time']} et enregistrée dans notre CRM.",
        "offerSlot": lambda slots: f"Souhaitez-vous réserver une démo de 20 minutes ? J'ai un créneau le {slots[0]['dayLabel']} à {slots[0]['time']}.",
        "askNeed": "Quel est votre principal défi aujourd’hui : délai de réponse, saisie CRM ou capacité de l’équipe ?",
        "askTeamTimeline": "Combien de commerciaux compte votre équipe et quel est votre calendrier de déploiement ?",
        "askAuthorityBudget": "Évaluez-vous cette solution pour votre équipe et avez-vous un budget mensuel prévu ?",
        "askEmail": "À quelle adresse e-mail puis-je envoyer l’invitation ?",
        "fallbackInfo": "NexaOps automatise la qualification vocale en temps réel avec RAG et synchronisation CRM instantanée.",
    },
    "de": {
        "greeting": "Hallo! Ich bin Aria von NexaCloud AI. Wie bearbeitet Ihr Vertriebsteam derzeit eingehende Leads?",
        "empathyPrefix": "Ich verstehe diesen Punkt vollkommen.",
        "bookedConfirm": lambda apt: f"Perfekt! Ihre Live-Demo ist für {apt['dayLabel']} um {apt['time']} bestätigt und im CRM gespeichert.",
        "offerSlot": lambda slots: f"Möchten Sie eine 20-minütige Live-Demo buchen? Ich habe am {slots[0]['dayLabel']} um {slots[0]['time']} einen Termin frei.",
        "askNeed": "Wo liegt aktuell Ihr größter Engpass: Reaktionszeit, manuelle CRM-Pflege oder Teamkapazität?",
        "askTeamTimeline": "Wie viele Vertriebsmitarbeiter hat Ihr Team und wann möchten Sie starten?",
        "askAuthorityBudget": "Entscheiden Sie für Ihr Team und welches monatliche Budget ist vorgesehen?",
        "askEmail": "An welche E-Mail-Adresse darf ich die Kalendereinladung senden?",
        "fallbackInfo": "NexaOps bietet Echtzeit-Sprachqualifizierung, RAG-gestützte Antworten und direkte CRM-Terminbuchung.",
    },
}


class SalesVoiceAgent:
    """Orchestrates multilingual STT turns, Hybrid RAG, BANT qualification, CRM booking, and summaries."""

    def __init__(
        self,
        *,
        retriever: HybridRetriever,
        session_store: SessionStore,
        crm_store: CRMStore,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.retriever = retriever
        self.session_store = session_store
        self.crm_store = crm_store
        cfg = config or {}
        self.config: dict[str, str] = {
            "provider": cfg.get("provider") or os.environ.get("LLM_PROVIDER", "auto"),
            "geminiApiKey": cfg.get("geminiApiKey") or os.environ.get("GEMINI_API_KEY", ""),
            "geminiModel": cfg.get("geminiModel") or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            "openaiApiKey": cfg.get("openaiApiKey") or os.environ.get("OPENAI_API_KEY", ""),
            "openaiModel": cfg.get("openaiModel") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        }

    def get_active_provider_name(self) -> str:
        provider = self.config["provider"]
        if provider == "local":
            return "Python Hybrid RAG Engine (Offline/Demo)"
        if provider in ("gemini", "auto") and self.config["geminiApiKey"]:
            return f"Gemini ({self.config['geminiModel']})"
        if provider in ("openai", "auto") and self.config["openaiApiKey"]:
            return f"OpenAI ({self.config['openaiModel']})"
        return "Python Hybrid RAG Engine (Offline/Demo)"

    def update_runtime_config(self, patch: dict[str, Any]) -> None:
        for key in ("provider", "geminiApiKey", "openaiApiKey", "geminiModel", "openaiModel"):
            if key in patch and patch[key] is not None:
                self.config[key] = str(patch[key])

    def start_call(
        self,
        *,
        language: str = "en",
        prospect_name: str | None = None,
        source: str = "Inbound Voice WebRTC",
    ) -> dict[str, Any]:
        session = self.session_store.create_session(language=language, prospect_name=prospect_name, source=source)
        phrases = LOCALIZED_PHRASES.get(language, LOCALIZED_PHRASES["en"])
        greeting = (
            f"Hi {prospect_name}! I'm Aria from NexaCloud AI. How is your sales team handling inbound lead follow-ups today?"
            if prospect_name and language == "en"
            else phrases["greeting"]
        )
        self.session_store.append_turn(session["id"], role="assistant", text=greeting, language=language, latency_ms=10)
        return {
            "session": session,
            "reply": greeting,
            "languageMeta": get_language_meta(language),
            "provider": self.get_active_provider_name(),
        }

    def process_turn(self, session_id: str, user_text: str) -> dict[str, Any]:
        t0 = time.perf_counter()
        session = self.session_store.get_session(session_id)
        if not session:
            raise KeyError(f"Session not found: {session_id}")

        detected_lang = detect_language(user_text, session["language"])
        analysis = analyze_turn(user_text, session["profile"])
        rag_hits = self.retriever.retrieve(user_text, top_k=3, min_score=0.08)

        self.session_store.append_turn(
            session_id,
            role="user",
            text=user_text,
            language=detected_lang,
            sentiment=analysis["sentiment"],
            intents=analysis["intents"],
            rag_hits=rag_hits,
        )
        self.session_store.update_profile(session_id, analysis["updates"])
        updated = self.session_store.get_session(session_id)

        available_slots = self.crm_store.get_available_slots(3)
        wants_booking = "booking_intent" in analysis["intents"] or bool(
            re.search(r"\b(book|confirm|yes|sure|sounds good|go ahead|schedule|lock it|tomorrow|10|2|4:30|haan|sí|oui|ja)\b", user_text, re.I)
        )
        asked_for_slot = any(
            t["role"] == "assistant" and re.search(r"openings on|demo|slot|कन्फर्म|डेमो|agendar", t["text"], re.I)
            for t in updated["turns"]
        )
        has_confirmation = bool(
            re.search(r"\b(10:00|10 am|2:00|2 pm|14:00|4:30|16:30|tomorrow|first slot|that works|book it|confirm|schedule it|lock)\b", user_text, re.I)
            or (asked_for_slot and re.search(r"\b(yes|sure|ok|okay|please|go ahead|works|haan|sí|oui)\b", user_text, re.I))
        )

        booking_action = None
        if not updated["profile"].get("appointmentBooked") and has_confirmation and available_slots:
            matched_slot = self._match_requested_slot(user_text, available_slots) or available_slots[0]
            lead = self.crm_store.upsert_lead_from_session(updated)
            book_res = self.crm_store.book_appointment(
                session_id=updated["id"],
                lead_id=lead["id"],
                prospect_name=updated["profile"].get("name"),
                email=updated["profile"].get("email"),
                company=updated["profile"].get("company"),
                slot_id=matched_slot["slotId"],
                notes=f"Booked autonomously during AI voice call. BANT={updated['bant']['score']}",
            )
            if book_res["ok"]:
                booking_action = {"type": "appointment_booked", "appointment": book_res["appointment"]}
                self.session_store.update_profile(session_id, {"appointmentBooked": book_res["appointment"]})

        final_session = self.session_store.get_session(session_id)
        provider_used = self.get_active_provider_name()

        if self._should_use_cloud_llm():
            try:
                reply_text = self._generate_with_cloud_llm(
                    final_session, rag_hits, available_slots, booking_action, wants_booking
                )
            except Exception as exc:  # pragma: no cover - network/key fallback
                provider_used = f"Fallback Engine (Cloud LLM error: {exc})"
                reply_text = self._generate_local_reply(
                    final_session, analysis, rag_hits, available_slots, booking_action, wants_booking
                )
        else:
            reply_text = self._generate_local_reply(
                final_session, analysis, rag_hits, available_slots, booking_action, wants_booking
            )

        latency_ms = max(8, int((time.perf_counter() - t0) * 1000))
        self.session_store.append_turn(
            session_id,
            role="assistant",
            text=reply_text,
            language=detected_lang,
            rag_hits=rag_hits,
            latency_ms=latency_ms,
            action=booking_action,
        )
        lead = self.crm_store.upsert_lead_from_session(final_session)

        return {
            "session": final_session,
            "reply": reply_text,
            "languageMeta": get_language_meta(detected_lang),
            "analysis": analysis,
            "ragHits": rag_hits,
            "bookingAction": booking_action,
            "availableSlots": available_slots[:3],
            "lead": lead,
            "latencyMs": latency_ms,
            "provider": provider_used,
        }

    @staticmethod
    def _match_requested_slot(text: str, slots: list[dict[str, str]]) -> dict[str, str] | None:
        lower = text.lower()
        for slot in slots:
            if "10" in lower and "10:00" in slot["time"]:
                return slot
            if ("2:00" in lower or "2 pm" in lower or "14:00" in lower) and "02:00" in slot["time"]:
                return slot
            if ("4:30" in lower or "16:30" in lower) and "04:30" in slot["time"]:
                return slot
            if slot["dayLabel"][:3].lower() in lower:
                return slot
        return None

    def _should_use_cloud_llm(self) -> bool:
        if self.config["provider"] == "local":
            return False
        return bool(self.config["geminiApiKey"] or self.config["openaiApiKey"])

    def _generate_with_cloud_llm(
        self,
        session: dict[str, Any],
        rag_hits: list[dict[str, Any]],
        available_slots: list[dict[str, str]],
        booking_action: dict[str, Any] | None,
        wants_booking: bool,
    ) -> str:
        lang_meta = get_language_meta(session["language"])
        kb_ctx = (
            "\n".join(f"[{h['id']} | {h['title']}] {h['content']}" for h in rag_hits)
            if rag_hits
            else "No exact KB chunk matched; answer concisely about NexaOps without inventing prices."
        )
        slot_str = " or ".join(f"{s['dayLabel']} at {s['time']}" for s in available_slots[:2])
        system_prompt = "\n".join(
            [
                f"You are Aria, an Autonomous B2B AI Sales Voice Agent for {self.retriever.company} ({self.retriever.product}).",
                f"Respond ONLY in {lang_meta['label']} ({lang_meta['bcp47']}). Keep responses to 2-3 spoken sentences max, natural voice tone.",
                "Ground every claim strictly in the RAG Knowledge Context below.",
                f"Prospect Profile: {json.dumps(session['profile'])}",
                f"BANT: {session['bant']['score']}/100 ({session['bant']['tier']}).",
                (
                    f"BOOKING JUST CONFIRMED: {json.dumps(booking_action['appointment'])}."
                    if booking_action
                    else f"Available demo slots: {slot_str}."
                    if wants_booking and available_slots
                    else "Ask one natural follow-up question for a missing BANT item."
                ),
                f"RAG Knowledge Context:\n{kb_ctx}",
            ]
        )

        if self.config["provider"] in ("gemini", "auto") and self.config["geminiApiKey"]:
            model = self.config["geminiModel"]
            key = urllib.parse.quote(self.config["geminiApiKey"])
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            body = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [
                    {
                        "role": "model" if t["role"] == "assistant" else "user",
                        "parts": [{"text": t["text"]}],
                    }
                    for t in session["turns"][-8:]
                ],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 220},
            }
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if not text:
                raise RuntimeError("Empty Gemini response")
            return text

        if self.config["openaiApiKey"]:
            body = {
                "model": self.config["openaiModel"],
                "temperature": 0.4,
                "max_tokens": 220,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *[
                        {"role": "assistant" if t["role"] == "assistant" else "user", "content": t["text"]}
                        for t in session["turns"][-8:]
                    ],
                ],
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config['openaiApiKey']}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            if not text:
                raise RuntimeError("Empty OpenAI response")
            return text

        raise RuntimeError("No Cloud LLM key configured")

    def _generate_local_reply(
        self,
        session: dict[str, Any],
        analysis: dict[str, Any],
        rag_hits: list[dict[str, Any]],
        available_slots: list[dict[str, str]],
        booking_action: dict[str, Any] | None,
        wants_booking: bool,
    ) -> str:
        lang = session["language"] or "en"
        phrases = LOCALIZED_PHRASES.get(lang, LOCALIZED_PHRASES["en"])

        if booking_action and booking_action.get("type") == "appointment_booked":
            return phrases["bookedConfirm"](booking_action["appointment"])

        parts: list[str] = []
        if analysis["sentiment"]["label"] in ("Frustrated", "Skeptical") or analysis["objections"]:
            parts.append(phrases["empathyPrefix"])

        is_pure_greeting = analysis["intents"] == ["greeting"]
        if rag_hits and not is_pure_greeting:
            top = rag_hits[0]
            if lang == "en":
                parts.append(top["content"])
                if len(rag_hits) > 1 and rag_hits[1]["score"] >= 0.25 and rag_hits[1]["id"] != top["id"]:
                    parts.append(rag_hits[1]["content"])
            else:
                parts.append(f"{phrases['fallbackInfo']} ({top['title']}: {top['content']})")
        elif "greeting" in analysis["intents"] and not session["profile"].get("need") and len(session["turns"]) <= 3:
            parts.append(phrases["askNeed"])
            return " ".join(parts)

        profile = session["profile"]
        if (wants_booking or session["bant"]["score"] >= 55) and not profile.get("appointmentBooked") and available_slots:
            if not profile.get("email") and session["bant"]["score"] >= 70 and wants_booking:
                parts.append(f"{phrases['offerSlot'](available_slots)} {phrases['askEmail']}")
            else:
                parts.append(phrases["offerSlot"](available_slots))
        elif session["bant"]["missing"]:
            if not profile.get("need"):
                parts.append(phrases["askNeed"])
            elif not profile.get("teamSize") or not profile.get("timeline"):
                parts.append(phrases["askTeamTimeline"])
            else:
                parts.append(phrases["askAuthorityBudget"])
        elif not profile.get("appointmentBooked") and available_slots:
            parts.append(phrases["offerSlot"](available_slots))

        return " ".join(parts) if parts else phrases["fallbackInfo"]

    def end_call_and_summarize(self, session_id: str) -> dict[str, Any]:
        session = self.session_store.close_session(session_id)
        lead = self.crm_store.upsert_lead_from_session(session)

        hist = session["sentimentHistory"]
        avg_sentiment = round(sum(s["score"] for s in hist) / len(hist), 2) if hist else 0.0
        sentiment_label = "Positive" if avg_sentiment >= 0.3 else "Frustrated" if avg_sentiment <= -0.3 else "Neutral"

        p = session["profile"]
        objections = p.get("objections") or []
        apt = p.get("appointmentBooked")

        role_part = f" ({p['role']})" if p.get("role") else ""
        company_part = f" at {p['company']}" if p.get("company") else ""
        summary_lines = [
            f"{p.get('name') or 'Prospect'}{role_part}{company_part} "
            f"completed an AI voice discovery call ({len(session['turns'])} turns, language: {get_language_meta(session['language'])['label']}).",
            f"Qualification: {session['bant']['score']}/100 ({session['bant']['tier']}). "
            f"Need: {p.get('need') or 'Workflow automation exploration'}. "
            f"Team size: {p.get('teamSize') or 'TBD'}. Timeline: {p.get('timeline') or 'TBD'}. Budget: {p.get('budget') or 'TBD'}.",
            f"Objections addressed via RAG: {', '.join(objections)}." if objections else "No major objections raised.",
            (
                f"Outcome: Live demo confirmed for {apt['dayLabel']} at {apt['time']} ({apt['meetingLink']})."
                if apt
                else "Outcome: Follow-up nurture required to lock in a demo slot."
            ),
        ]

        top_topics = " & ".join(c["title"] for c in session["ragCitations"][:2]) or "product overview"
        next_best_action = (
            f"Send pre-demo agenda and {top_topics} to {p.get('email') or 'prospect'}."
            if apt
            else "Assign to Senior AE for immediate calendar confirmation within 2 hours."
            if session["bant"]["tier"] == "Hot"
            else "Enroll in 14-day Proof of Value email + voice follow-up sequence."
        )

        follow_up_lines = [
            f"Subject: Next steps with {self.retriever.company} — {p.get('company') or 'Your Sales Automation Demo'}",
            "",
            f"Hi {p.get('name') or 'there'},",
            "",
            f"Great speaking with you today! Based on our conversation about {p.get('need') or 'automating inbound lead response'}, here is a quick recap:",
            (
                f"- Confirmed Demo: {apt['dayLabel']} at {apt['time']} ({apt['meetingLink']})"
                if apt
                else "- Recommended Next Step: 14-day guided Proof of Value pilot"
            ),
        ]
        if session["ragCitations"]:
            follow_up_lines.append(
                f"- Topics Covered: {', '.join(c['title'] for c in session['ragCitations'])}"
            )
        follow_up_lines.extend(["", "Best regards,", f"Aria | Autonomous Sales Advisor, {self.retriever.company}"])

        summary = {
            "id": f"sum-{uuid.uuid4().hex[:8]}",
            "sessionId": session["id"],
            "leadId": lead["id"],
            "prospectName": p.get("name") or "Anonymous Prospect",
            "company": p.get("company") or "Unknown Company",
            "language": session["language"],
            "bantScore": session["bant"]["score"],
            "tier": session["bant"]["tier"],
            "avgSentiment": avg_sentiment,
            "sentimentLabel": sentiment_label,
            "objections": objections,
            "ragCitations": [
                {"id": c["id"], "title": c["title"], "score": c["score"]} for c in session["ragCitations"]
            ],
            "appointmentBooked": bool(apt),
            "appointment": apt,
            "executiveSummary": " ".join(summary_lines),
            "nextBestAction": next_best_action,
            "followUpEmail": "\n".join(follow_up_lines),
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        self.crm_store.save_call_summary(summary)
        return {"session": session, "lead": lead, "summary": summary}
