# NexaCloud AI — Important Files Manifest & Deployment Guide

## 1. Consolidated Package
All important production, frontend, test, documentation, and deployment files have been packaged into:
- `dist/nexacloud-ai-sales-voice-agent-python.zip`

## 2. Important Files Included

### Core Application & Server
- `app.py` — Main Python entrypoint (`run_server`).
- `sales_agent/server.py` — Threaded HTTP + Server-Sent Events (SSE) server, REST API router, and static UI host (`HOST` / `PORT` configurable).
- `sales_agent/agent/sales_agent.py` — Autonomous AI Sales Voice Agent orchestrator (multilingual turns, RAG grounding, booking tool execution, Gemini/OpenAI or local fallback, call summaries).

### AI, RAG, Memory & CRM Engines
- `sales_agent/rag/retriever.py` — Hybrid **BM25 + `scikit-learn` TF-IDF** cosine similarity RAG retriever.
- `sales_agent/intelligence/analyzer.py` — Real-time BANT entity extraction, 0–100 qualification scoring, sentiment analysis, and objection detection.
- `sales_agent/memory/session_store.py` — Thread-safe contextual session memory with PII-redacted turn logs.
- `sales_agent/crm/crm_store.py` — SQLite CRM repository (`leads`, `appointments`, `call_summaries`, `webhook_outbox`) with conflict-checked slot booking and KPIs.
- `sales_agent/utils/language.py` — Multilingual detection (`en`, `hi`, `es`, `fr`, `de`).
- `sales_agent/utils/pii.py` — PII redaction (SSN, card, email, phone).
- `sales_agent/utils/env.py` — Lightweight `.env` loader.

### Frontend Web UI & Knowledge Base
- `public/index.html` — Obsidian & Champagne Gold Glassmorphism UI (Voice Studio, CRM & Insights, RAG Knowledge Base, Architecture Diagram).
- `public/styles.css` — Responsive luxury dark glass styling.
- `public/app.js` — Web Speech API STT/TTS, barge-in, mirrored gradient waveform, SSE live sync, and 1-click prospect simulator.
- `data/knowledge_base.json` — Product, pricing, security (SOC 2 / GDPR), ROI, integration, and onboarding knowledge chunks.

### Tests, Demo & Documentation
- `tests/test_agent.py` — Unit and full in-process HTTP integration tests (`unittest`).
- `scripts/e2e_demo.py` — Scripted 4-turn end-to-end demo.
- `README.md` & `docs/ARCHITECTURE.md` — Architecture diagram, 100k-user scalability plan, security controls, and cost breakdown.

### Deployment Configurations
- `Dockerfile` & `.dockerignore` — Container image build (`HOST=0.0.0.0`, `PORT=3000`).
- `render.yaml` — Render 1-click web service blueprint.
- `Procfile` — Railway / Heroku / Buildpack start command.
- `requirements.txt`, `pyproject.toml`, `.env.example` — Dependencies and environment template.

---

## 3. How to Deploy

### Option A: Deploy on Render (Free Tier via GitHub)
1. Create a GitHub repository and push this folder:
   ```powershell
   git remote add origin https://github.com/<your-user>/nexacloud-voice-agent.git
   git push -u origin main
   ```
2. Go to **Render → New → Blueprint** (or **Web Service**), connect your repo, and Render will auto-detect `render.yaml` (`pip install -r requirements.txt` & `HOST=0.0.0.0 python app.py`).
3. Optional: Add `GEMINI_API_KEY` or `OPENAI_API_KEY` in Render Environment Variables.

### Option B: Deploy via Docker (Any Cloud / VPS)
```bash
docker build -t nexacloud-voice-agent .
docker run -p 3000:3000 -e HOST=0.0.0.0 nexacloud-voice-agent
```

### Option C: Deploy ZIP Directly
Upload `dist/nexacloud-ai-sales-voice-agent-python.zip` to Azure App Service, AWS Elastic Beanstalk, or extract on any Python 3.11+ server and run:
```bash
pip install -r requirements.txt
HOST=0.0.0.0 PORT=3000 python app.py
```
