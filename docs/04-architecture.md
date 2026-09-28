# System Architecture

```text
User
  |
  v
React + TypeScript
  |
  v
FastAPI API
  |
  v
Conversation Orchestrator
  |
  +--> Intent / routing
  |
  +--> Conversation Memory ----> PostgreSQL / Redis
  |
  +--> General Conversation ----> LLM Provider
  |
  +--> University RAG
  |       |
  |       +--> LlamaIndex
  |       +--> ChromaDB
  |       +--> University documents
  |
  +--> Authenticated Tools/APIs (future)
          |
          +--> timetable
          +--> attendance
          +--> results
          +--> fees

LLM Provider interface:
    Ollama/local model
          OR
    compatible cloud provider
```

## Design principles
- Provider abstraction for LLM and embeddings.
- Retrieval is separate from generation.
- University sources remain traceable.
- Conversation memory is separate from factual knowledge.
- Student-specific data requires authorization.
