"""Threaded HTTP + Server-Sent Events (SSE) server and testable request dispatcher."""

from __future__ import annotations

import json
import mimetypes
import os
import queue
import re
import threading
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from sales_agent.agent.sales_agent import SalesVoiceAgent
from sales_agent.crm.crm_store import CRMStore
from sales_agent.memory.session_store import SessionStore
from sales_agent.rag.retriever import HybridRetriever
from sales_agent.utils.env import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

_MIME_OVERRIDES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


class AppContext:
    """Application container holding RAG, memory, SQLite CRM, Agent, and SSE subscribers."""

    def __init__(
        self,
        *,
        kb_path: str | Path | None = None,
        crm_db_path: str | Path | None = None,
        public_dir: str | Path | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        load_dotenv(ROOT_DIR / ".env")
        self.kb_path = Path(kb_path) if kb_path else ROOT_DIR / "data" / "knowledge_base.json"
        self.crm_db_path = Path(crm_db_path) if crm_db_path else ROOT_DIR / "data" / "crm.db"
        self.public_dir = Path(public_dir) if public_dir else ROOT_DIR / "public"

        self.retriever = HybridRetriever(self.kb_path)
        self.session_store = SessionStore()
        self.crm_store = CRMStore(self.crm_db_path)
        self.agent = SalesVoiceAgent(
            retriever=self.retriever,
            session_store=self.session_store,
            crm_store=self.crm_store,
            config=config,
        )

        self._sse_lock = threading.Lock()
        self._sse_clients: set[queue.Queue[str]] = set()

    def register_sse(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue(maxsize=64)
        with self._sse_lock:
            self._sse_clients.add(q)
        return q

    def unregister_sse(self, q: queue.Queue[str]) -> None:
        with self._sse_lock:
            self._sse_clients.discard(q)

    def broadcast(self, event: str, data: Any) -> None:
        packet = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        with self._sse_lock:
            for q in list(self._sse_clients):
                try:
                    q.put_nowait(packet)
                except queue.Full:
                    pass

    def dispatch(self, method: str, raw_path: str, body_bytes: bytes = b"") -> tuple[int, str, bytes]:
        """Pure in-process HTTP router returning (status_code, content_type, body_bytes)."""
        parsed = urllib.parse.urlsplit(raw_path)
        pathname = parsed.path

        try:
            body: dict[str, Any] = {}
            if body_bytes.strip():
                body = json.loads(body_bytes.decode("utf-8"))

            if method == "GET" and pathname == "/api/health":
                active_count = sum(1 for s in self.session_store.list_sessions() if s["status"] == "active")
                return self._json(
                    200,
                    {
                        "ok": True,
                        "runtime": "Python",
                        "provider": self.agent.get_active_provider_name(),
                        "kbChunks": len(self.retriever.list_chunks()),
                        "activeSessions": active_count,
                        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    },
                )

            if method == "POST" and pathname == "/api/config":
                self.agent.update_runtime_config(body)
                provider = self.agent.get_active_provider_name()
                self.broadcast("config_updated", {"provider": provider})
                return self._json(200, {"ok": True, "provider": provider})

            if method == "GET" and pathname == "/api/kb":
                return self._json(
                    200,
                    {
                        "company": self.retriever.company,
                        "product": self.retriever.product,
                        "chunks": self.retriever.list_chunks(),
                    },
                )

            if method == "POST" and pathname == "/api/kb":
                if not body.get("title") or not body.get("content"):
                    return self._json(400, {"error": "title and content are required"})
                chunk = self.retriever.add_chunk(
                    title=str(body["title"]),
                    content=str(body["content"]),
                    category=str(body.get("category") or "custom"),
                    tags=list(body.get("tags") or []),
                )
                self.broadcast("kb_updated", {"chunk": chunk})
                return self._json(201, {"ok": True, "chunk": chunk})

            if method == "POST" and pathname == "/api/calls/start":
                res = self.agent.start_call(
                    language=str(body.get("language") or "en"),
                    prospect_name=body.get("prospectName"),
                    source=str(body.get("source") or "Inbound Voice WebRTC"),
                )
                self.broadcast("call_started", {"sessionId": res["session"]["id"]})
                return self._json(201, res)

            turn_match = re.match(r"^/api/calls/([^/]+)/turn$", pathname)
            if method == "POST" and turn_match:
                session_id = urllib.parse.unquote(turn_match.group(1))
                text = str(body.get("text") or "").strip()
                if not text:
                    return self._json(400, {"error": "text is required"})
                res = self.agent.process_turn(session_id, text)
                self.broadcast("crm_updated", self.crm_store.get_all_data())
                return self._json(200, res)

            end_match = re.match(r"^/api/calls/([^/]+)/end$", pathname)
            if method == "POST" and end_match:
                session_id = urllib.parse.unquote(end_match.group(1))
                res = self.agent.end_call_and_summarize(session_id)
                self.broadcast("crm_updated", self.crm_store.get_all_data())
                return self._json(200, res)

            session_match = re.match(r"^/api/calls/([^/]+)$", pathname)
            if method == "GET" and session_match:
                session_id = urllib.parse.unquote(session_match.group(1))
                session = self.session_store.get_session(session_id)
                if not session:
                    return self._json(404, {"error": "Session not found"})
                return self._json(200, {"session": session})

            if method == "GET" and pathname == "/api/crm":
                return self._json(200, self.crm_store.get_all_data())

            if method == "POST" and pathname == "/api/crm/book":
                res = self.crm_store.book_appointment(
                    session_id=str(body.get("sessionId") or ""),
                    lead_id=body.get("leadId"),
                    prospect_name=body.get("prospectName"),
                    email=body.get("email"),
                    company=body.get("company"),
                    slot_id=body.get("slotId"),
                    date=body.get("date"),
                    time=body.get("time"),
                    notes=str(body.get("notes") or ""),
                )
                if not res["ok"]:
                    return self._json(409, res)
                self.broadcast("crm_updated", self.crm_store.get_all_data())
                return self._json(201, res)

            if method == "GET":
                rel = "index.html" if pathname == "/" else pathname.lstrip("/")
                target = (self.public_dir / rel).resolve()
                public_root = self.public_dir.resolve()
                if public_root not in target.parents and target != public_root:
                    return self._json(403, {"error": "Forbidden"})
                if target.exists() and target.is_file():
                    mime = _MIME_OVERRIDES.get(target.suffix.lower()) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                    return 200, mime, target.read_bytes()

            return self._json(404, {"error": "Not found"})
        except KeyError as exc:
            return self._json(404, {"error": str(exc)})
        except Exception as exc:
            return self._json(500, {"error": str(exc)})

    @staticmethod
    def _json(status: int, payload: Any) -> tuple[int, str, bytes]:
        return status, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode("utf-8")


def make_handler(app: AppContext) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            # Quiet clean stdout for demo readability
            pass

        def do_GET(self) -> None:  # noqa: N802
            if urllib.parse.urlsplit(self.path).path == "/api/events":
                self._handle_sse()
                return
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

        def _handle(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body_bytes = self.rfile.read(length) if length > 0 else b""
            status, ctype, resp_bytes = app.dispatch(method, self.path, body_bytes)
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(resp_bytes)

        def _handle_sse(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            q = app.register_sse()
            try:
                hello = f"event: connected\ndata: {json.dumps({'provider': app.agent.get_active_provider_name()})}\n\n"
                self.wfile.write(hello.encode("utf-8"))
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=15)
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                app.unregister_sse(q)

    return RequestHandler


def run_server(host: str | None = None, port: int | None = None) -> None:
    app = AppContext()
    listen_host = host or os.environ.get("HOST", "127.0.0.1")
    listen_port = port or int(os.environ.get("PORT", "3000"))
    server = ThreadingHTTPServer((listen_host, listen_port), make_handler(app))
    print(f"[NexaCloud AI Python Voice Agent] Listening at http://{listen_host}:{listen_port}", flush=True)
    print(f"[Active Brain] {app.agent.get_active_provider_name()}", flush=True)
    print(f"[SQLite CRM] {app.crm_db_path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()
        app.crm_store.close()
