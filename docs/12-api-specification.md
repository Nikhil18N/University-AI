# API Specification

## Auth
POST /api/v1/auth/login
POST /api/v1/auth/register
POST /api/v1/auth/refresh

## Chat
POST /api/v1/chat
POST /api/v1/chat/stream
GET /api/v1/conversations
GET /api/v1/conversations/{conversation_id}
DELETE /api/v1/conversations/{conversation_id}

## Feedback
POST /api/v1/feedback

## Deterministic finance tools
POST /api/v1/finance/estimate
GET /api/v1/admin/finance-rules
PUT /api/v1/admin/finance-rules
GET /api/v1/admin/agent-runs
GET /api/v1/admin/calculations

Finance estimates are calculated only from versioned official rules in the finance
catalog. If a matching fee or scholarship rule is unavailable, the endpoint returns
`status: "insufficient_data"` rather than inventing an amount.
The admin endpoints require `X-Admin-Key` and publish the validated catalog atomically.

## Memory controls
GET /api/v1/memory?session_id=...
POST /api/v1/memory
DELETE /api/v1/memory/{key}
GET /api/v1/memory/conversations/{conversation_id}/summary?session_id=...
GET /api/v1/memory/calculations?session_id=...
DELETE /api/v1/memory/calculations?session_id=...

Memory writes require explicit consent and are limited to non-sensitive preferences.
Raw messages remain the source of truth; summaries are bounded context and are
deleted with their conversation.

The chat orchestrator routes explicit calculation requests containing fee or
scholarship intent to this deterministic tool. Ordinary informational questions
continue through the existing intent/RAG/LLM path. Responses expose an optional
`agent` field such as `{ "agent": "finance", "status": "executed" }`.

Agent execution is bounded by an allowlisted tool registry and a maximum of
three steps. The model cannot invoke arbitrary endpoints or services.
Each agent execution is also persisted in `agent_runs` with its route, selected
tool, policy reason, status, step count, conversation, and response message.
Administrators can inspect recent records through `/api/v1/admin/agent-runs`.
Finance calculations additionally persist their explicit inputs, result status,
result payload, source references, and originating message in
`calculation_scenarios`.
When required finance inputs are missing, the agent stores a pending
`pending_agent_tasks` record and resumes it when the user supplies the missing
details in the same conversation.

Pending clarification tasks can be listed with
`GET /api/v1/memory/pending-tasks?session_id=...` and cancelled with
`DELETE /api/v1/memory/pending-tasks/{conversation_id}?session_id=...`.
Both endpoints enforce browser-session ownership.
Administrators can inspect recent scenarios through `/api/v1/admin/calculations`.
Users can inspect only their own session's calculations through
`/api/v1/memory/calculations`.
They can delete that calculation history without deleting the associated chat
conversation through `DELETE /api/v1/memory/calculations`.

## Admin
POST /api/v1/admin/documents
GET /api/v1/admin/documents
POST /api/v1/admin/documents/{id}/reindex
DELETE /api/v1/admin/documents/{id}
GET /api/v1/admin/stats
GET /api/v1/admin/feedback
GET /api/v1/admin/conversations
GET /api/v1/admin/conversations/export
GET /api/v1/admin/conversations/{conversation_id}
DELETE /api/v1/admin/conversations/{conversation_id}
POST /api/v1/admin/exemplars/promote



## Chat request example

```json
{
  "session_id": "browser-session-uuid",
  "conversation_id": "uuid-or-null",
  "message": "When is exam registration?"
}
```

## Chat response example

```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "answer": "According to ...",
  "sources": [
    {
      "document_id": "uuid",
      "title": "Academic Calendar",
      "page": 4
    }
  ],
  "suggestions": [
    "📋 How to Apply",
    "💰 Fee Structure"
  ],
  "cards": [
    {
      "type": "video_recommendations",
      "title": "Official SR University Video Tours",
      "channel_name": "SR University Official",
      "channel_url": "https://www.youtube.com/@SRUniversity/videos",
      "videos": [
        {
          "id": "9kYIkkadZkU",
          "title": "SR University Campus Tour",
          "url": "https://www.youtube.com/watch?v=9kYIkkadZkU",
          "thumbnail_url": "https://img.youtube.com/vi/9kYIkkadZkU/hqdefault.jpg",
          "category": "Campus Tour",
          "duration": "3:45"
        }
      ]
    }
  ],
  "flow": null,
  "model": "gemini-3.5-flash-lite"
}
```

## Chat SSE Stream format
`POST /api/v1/chat/stream` returns `text/event-stream` chunks:
- `data: {"type": "start", "conversation_id": "uuid"}`
- `data: {"type": "token", "delta": "word "}`
- `data: {"type": "done", "conversation_id": "uuid", "message_id": "uuid", "answer": "...", "sources": [...], "suggestions": [...], "cards": [...], "flow": null, "model": "..."}`

## Feedback request example

```json
{
  "session_id": "browser-session-uuid",
  "conversation_id": "uuid",
  "message_id": "uuid",
  "rating": 1,
  "comment": "Accurate and clear answer."
}
```

## Feedback response example

```json
{
  "id": "uuid",
  "status": "received"
}
```

## Public Access Model
For public anonymous access, endpoints use `session_id` (a browser-generated UUID stored in localStorage) to track conversations and feedback without requiring student login or signup. Admin endpoints (`/api/v1/admin/*`) require the `X-Admin-Key` header.
GET `/api/v1/admin/feedback` returns feedback items with `question` and `answer` context. Positive feedback (rating=1) automatically indexes the Q&A into ChromaDB collection `verified_exemplars` for dynamic few-shot self-improvement.

## Model Evaluation & Benchmark Endpoints (Admin Only)
- `POST /api/v1/admin/evaluations/run`: Executes benchmark suite from `evaluation/evaluation_dataset.jsonl` against RAG and stores results in `evaluation_records`.
- `GET /api/v1/admin/evaluations`: Paginated list of benchmark and response evaluation records with groundedness scores, latencies, and pass/fail indicators.

Use consistent error schemas and HTTP status codes.
