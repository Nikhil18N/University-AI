# University AI Companion — Vibe Coding Documentation

This documentation package defines the product, architecture, AI behavior, RAG pipeline,
API contracts, security, testing, deployment, and coding-agent rules for a University AI
Companion / Conversation Bot.

## Core concept
The system is a conversational companion that can:
- Handle greetings and casual conversation
- Answer university-specific questions using RAG
- Maintain conversation context
- Optionally access authenticated student services
- Support multilingual conversation
- Refuse to invent unverified university information

## Recommended initial stack
- Frontend: React + TypeScript
- Backend: Python + FastAPI
- LLM: Local model through Ollama (provider abstraction required)
- RAG: LlamaIndex
- Vector DB: ChromaDB
- Document processing: PyMuPDF + Unstructured
- Relational DB: PostgreSQL
- Cache/session support: Redis
- Deployment: Docker

Read `AGENTS.md` before implementing code.
Start with the MVP roadmap in `docs/23-roadmap.md`.

## Quickstart

### 1. Start Infrastructure (Docker)
```bash
docker-compose up -d
```
This spins up PostgreSQL (port 5433), Redis (port 6379), and ChromaDB (port 8000).

### 2. Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 3. Run Backend Tests
```bash
cd backend
.\venv\Scripts\pytest -v
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The frontend starts at `http://localhost:5173` and connects directly to the backend at `http://localhost:8080` without requiring login or signup.
