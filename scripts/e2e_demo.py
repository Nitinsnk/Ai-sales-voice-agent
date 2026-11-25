"""Scripted 4-turn end-to-end demo for the Python Autonomous AI Sales Voice Agent."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sales_agent.server import AppContext  # noqa: E402


def main() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="nexa-py-e2e-")
    kb_path = Path(tmp_dir) / "kb.json"
    crm_path = Path(tmp_dir) / "crm.db"
    shutil.copy(ROOT_DIR / "data" / "knowledge_base.json", kb_path)

    app = AppContext(kb_path=kb_path, crm_db_path=crm_path)
    try:
        print("=== NexaCloud AI — Autonomous Sales Voice Agent (Python E2E Demo) ===\n")
        start = app.agent.start_call(language="en")
        sid = start["session"]["id"]
        print(f"[Session] {sid} | Brain: {start['provider']}")
        print(f"[Aria]: {start['reply']}\n")

        turns = [
            "Hi, I'm Priya Nair, VP of Sales at VelocityTech. We have 35 sales reps and slow lead response. We need a solution this month.",
            "Is your platform SOC 2 compliant and what does the Growth tier cost?",
            "Okay, $899/month fits our budget. My email is priya@velocitytech.io. Please book tomorrow at 10:00 AM.",
            "Namaste, kya aap Hindi mein bata sakte hain ki onboarding kitna samay leta hai?",
        ]

        for text in turns:
            print(f"[Prospect]: {text}")
            res = app.agent.process_turn(sid, text)
            top_rag = res["ragHits"][0]["title"] if res["ragHits"] else "None"
            print(f"[Aria ({res['languageMeta']['label']}, {res['latencyMs']}ms)]: {res['reply']}")
            print(
                f"  -> BANT: {res['session']['bant']['score']}/100 ({res['session']['bant']['tier']}) | "
                f"Sentiment: {res['analysis']['sentiment']['label']} | RAG Top: {top_rag}"
            )
            if res["bookingAction"]:
                apt = res["bookingAction"]["appointment"]
                print(f"  -> [AUTO-BOOKED] {apt['dayLabel']} at {apt['time']} | Link: {apt['meetingLink']}")
            print("")

        end_res = app.agent.end_call_and_summarize(sid)
        print("=== Post-Call Executive Summary ===")
        print(end_res["summary"]["executiveSummary"])
        print("\n=== Next Best Action ===")
        print(end_res["summary"]["nextBestAction"])
        print("\n=== Auto-Drafted Follow-up Email ===")
        print(end_res["summary"]["followUpEmail"])
    finally:
        app.crm_store.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
