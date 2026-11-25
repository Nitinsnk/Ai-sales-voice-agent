"""Unit and full in-process HTTP integration tests for the Python AI Sales Voice Agent."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sales_agent.intelligence.analyzer import analyze_turn, calculate_bant
from sales_agent.server import AppContext
from sales_agent.utils.language import detect_language
from sales_agent.utils.pii import redact_pii

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestCoreIntelligence(unittest.TestCase):
    def test_multilingual_detection(self) -> None:
        self.assertEqual(detect_language("Namaste, kya aap Hindi mein baat kar sakte hain?", "en"), "hi")
        self.assertEqual(detect_language("Hola, ¿cuál es el precio para mi empresa?", "en"), "es")
        self.assertEqual(detect_language("Our team has 30 sales reps.", "en"), "en")

    def test_pii_redaction(self) -> None:
        masked = redact_pii("Contact me at john.doe@acme.com or +1 415-555-0199.")
        self.assertNotIn("john.doe@acme.com", masked)
        self.assertNotIn("415-555-0199", masked)
        self.assertIn("[REDACTED_PHONE]", masked)

    def test_bant_extraction_and_scoring(self) -> None:
        res = analyze_turn(
            "Hi, I'm Priya Nair, VP of Sales at VelocityTech. We have 35 sales reps and slow lead response. We need this this month and $899/mo works."
        )
        u = res["updates"]
        self.assertEqual(u["name"], "Priya Nair")
        self.assertEqual(u["company"], "VelocityTech")
        self.assertEqual(u["teamSize"], 35)
        self.assertTrue(u.get("budget"))
        self.assertTrue(u.get("authority"))
        self.assertTrue(u.get("timeline"))
        bant = calculate_bant(u)
        self.assertGreaterEqual(bant["score"], 90)
        self.assertEqual(bant["tier"], "Hot")


class TestEndToEndAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="nexa-py-test-")
        self.kb_path = Path(self.tmp_dir) / "kb.json"
        self.crm_path = Path(self.tmp_dir) / "crm.db"
        shutil.copy(ROOT_DIR / "data" / "knowledge_base.json", self.kb_path)
        self.app = AppContext(kb_path=self.kb_path, crm_db_path=self.crm_path, config={"provider": "local"})

    def tearDown(self) -> None:
        self.app.crm_store.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        raw = json.dumps(body).encode("utf-8") if body is not None else b""
        status, _, resp_bytes = self.app.dispatch(method, path, raw)
        return status, json.loads(resp_bytes.decode("utf-8"))

    def test_full_sales_workflow(self) -> None:
        # 1. Health check & static HTML check
        status, health = self._call("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(health["ok"])
        self.assertEqual(health["runtime"], "Python")
        self.assertGreaterEqual(health["kbChunks"], 8)

        html_status, html_mime, html_bytes = self.app.dispatch("GET", "/")
        self.assertEqual(html_status, 200)
        self.assertIn("text/html", html_mime)
        self.assertIn(b"NexaCloud AI", html_bytes)

        # 2. Start call
        status, start = self._call("POST", "/api/calls/start", {"language": "en"})
        self.assertEqual(status, 201)
        sid = start["session"]["id"]
        self.assertTrue(sid.startswith("call-"))

        # 3. Turn 1: Prospect intro + pain + role + timeline
        status, t1 = self._call(
            "POST",
            f"/api/calls/{sid}/turn",
            {"text": "I'm Rohan Verma, Head of Sales at CloudAxis. We have 25 reps with slow lead response and want to launch this month."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(t1["session"]["profile"]["name"], "Rohan Verma")
        self.assertEqual(t1["session"]["profile"]["company"], "CloudAxis")
        self.assertEqual(t1["session"]["profile"]["teamSize"], 25)
        self.assertGreaterEqual(t1["session"]["bant"]["score"], 70)

        # 4. Turn 2: Security & pricing RAG query
        status, t2 = self._call(
            "POST",
            f"/api/calls/{sid}/turn",
            {"text": "Is your platform SOC 2 compliant and what does Growth pricing cost?"},
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(t2["ragHits"]), 1)
        self.assertRegex(t2["reply"], r"(?i)SOC 2|899|Starter|Growth")

        # 5. Turn 3: Budget + automated booking
        status, t3 = self._call(
            "POST",
            f"/api/calls/{sid}/turn",
            {"text": "Great, $899/month fits our budget and my email is rohan@cloudaxis.io. Please book tomorrow at 10:00 AM."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(t3["bookingAction"]["type"], "appointment_booked")
        self.assertEqual(t3["bookingAction"]["appointment"]["time"], "10:00 AM")

        # 6. End call & summarize
        status, end_res = self._call("POST", f"/api/calls/{sid}/end", {})
        self.assertEqual(status, 200)
        self.assertTrue(end_res["summary"]["appointmentBooked"])
        self.assertIn("Rohan Verma", end_res["summary"]["followUpEmail"])

        # 7. Verify SQLite CRM & dynamic KB ingestion
        status, crm = self._call("GET", "/api/crm")
        self.assertEqual(status, 200)
        self.assertTrue(any(l["name"] == "Rohan Verma" and l["status"] == "Demo Booked" for l in crm["leads"]))
        self.assertGreaterEqual(len(crm["appointments"]), 1)
        self.assertTrue(any(w["eventType"] == "calendar.appointment.booked" for w in crm["webhookOutbox"]))

        status, kb_add = self._call(
            "POST",
            "/api/kb",
            {
                "title": "Q4 Healthcare HIPAA Add-on",
                "category": "security",
                "tags": ["hipaa", "healthcare", "baa"],
                "content": "NexaOps signs HIPAA Business Associate Agreements (BAA) on Growth and Enterprise tiers.",
            },
        )
        self.assertEqual(status, 201)
        self.assertTrue(kb_add["ok"])


if __name__ == "__main__":
    unittest.main()
