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

## Admin
POST /api/v1/admin/documents
GET /api/v1/admin/documents
POST /api/v1/admin/documents/{id}/reindex
DELETE /api/v1/admin/documents/{id}
GET /api/v1/admin/stats
GET /api/v1/admin/feedback

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
  "cards": [],
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

Use consistent error schemas and HTTP status codes.
