\# Autonomous AI Sales Voice Agent: Project Report



\## Business Problem

Sales teams lose leads when inbound calls go unanswered or are handled inconsistently. Qualifying prospects, answering product questions, and booking meetings take time that could go to closing deals.



\## Solution

NexaCloud AI is a prototype voice agent that handles a sales call end to end: it answers product questions from a knowledge base, captures and scores lead details (BANT: Budget, Authority, Need, Timeline), detects sentiment and objections, books non-conflicting appointments, and produces a call summary and follow-up email.



\## Technical Implementation

\- \*\*Voice:\*\* Browser Web Speech API for speech-to-text and text-to-speech; typed input as fallback.

\- \*\*Retrieval (RAG):\*\* Hybrid retriever combining BM25 lexical scoring with TF-IDF character n-gram cosine similarity (scikit-learn, with a pure-Python fallback).

\- \*\*Qualification:\*\* Entity extraction for name, company, role, team size, budget, and timeline; BANT score 0 to 100, labelled Hot, Warm, or Cold.

\- \*\*Intelligence:\*\* Per-turn sentiment and objection detection.

\- \*\*Memory and language:\*\* Session memory per call; language detection for en, hi, es, fr, de.

\- \*\*CRM:\*\* SQLite database with leads, appointments (unique date-time constraint prevents double-booking), call summaries, and a webhook outbox.

\- \*\*Server:\*\* Python ThreadingHTTPServer with REST APIs and Server-Sent Events. Runs fully offline, with optional Gemini or OpenAI integration.

\- \*\*Security:\*\* PII redaction in logs; secrets kept in environment variables, not in the repository.



\## Scalability to 100,000 Users

Move the stateless web tier behind a load balancer and run multiple instances. Replace SQLite with PostgreSQL, sessions with Redis, and the local retriever with a managed vector database. Put speech processing on a managed STT/TTS service, and queue webhook and CRM sync jobs. Details are in `docs/ARCHITECTURE.md`.



\## Commercial Feasibility

Priced per booked meeting or per seat, the product reduces the cost of inbound qualification. Main costs are speech APIs, LLM tokens, hosting, and database. These should be estimated for specific volumes before any launch.



\## Limitations and Next Steps

The current build uses a rule-based offline brain by default. Next steps: connect a live LLM, add telephony (for example, Twilio) for real phone calls, add a production CRM connector, and add authentication.

