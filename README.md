# NexaCloud AI — Autonomous AI Sales Voice Agent (Python MVP)

A functional **Python 3** prototype demonstrating an end-to-end **Autonomous AI Sales Voice Agent** with real-time STT/TTS, `scikit-learn` TF-IDF + BM25 Hybrid RAG, multilingual switching, live BANT lead qualification & sentiment analysis, SQLite CRM & calendar booking, and executive call summaries.

## Quick Start (Windows PowerShell)

```powershell
cd "C:\Users\S. NITIN KUMAR\.gemini\antigravity\scratch\ai-sales-voice-agent-python"
py app.py
# Open http://127.0.0.1:3000 in Chrome or Edge
```

Run automated tests (`unittest`):

```powershell
py -m unittest discover -s tests -v
```

Run the scripted 4-turn end-to-end demo:

```powershell
py scripts/e2e_demo.py
```

## Architecture & Project Structure

- `app.py` — Application entrypoint (`run_server`)
- `sales_agent/server.py` — Threaded HTTP + SSE server (`ThreadingHTTPServer`) & REST API dispatcher
- `sales_agent/agent/sales_agent.py` — Voice orchestrator (language, RAG, BANT, booking, Gemini/OpenAI or local fallback, call summary)
- `sales_agent/rag/retriever.py` — Hybrid **BM25 + `scikit-learn` TF-IDF cosine similarity** RAG retriever
- `sales_agent/intelligence/analyzer.py` — BANT entity extractor, qualification scorer, sentiment & objection detector
- `sales_agent/memory/session_store.py` — Thread-safe contextual session memory with PII-redacted logging
- `sales_agent/crm/crm_store.py` — **SQLite** CRM database (`data/crm.db`) for leads, conflict-checked appointments, summaries & webhook outbox
- `sales_agent/utils/language.py` & `sales_agent/utils/pii.py` — Multilingual detection (`en`, `hi`, `es`, `fr`, `de`) & PII redaction
- `public/` — Interactive Voice Studio, CRM & Insights Dashboard, RAG Knowledge Manager, and Architecture Viewer
- `docs/ARCHITECTURE.md` — Business case, Mermaid architecture diagram, 100k-user scalability plan, security & operational costs
