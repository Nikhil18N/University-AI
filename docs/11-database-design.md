# Database Design

## Core tables

### users
- id
- name
- email
- role
- password_hash or external_auth_id
- created_at
- updated_at

### conversations
- id
- user_id
- title
- created_at
- updated_at

### messages
- id
- conversation_id
- role
- content
- model
- created_at
- metadata

### documents
- id
- title
- source
- document_type
- status
- created_at
- updated_at

### document_versions
- id
- document_id
- version
- checksum
- effective_date
- publication_date
- storage_location
- indexed_at
- active

### feedback
- id
- user_id
- conversation_id
- message_id
- rating
- comment
- created_at

Use migrations. Production startup does not create tables automatically; run
`cd backend && alembic upgrade head` during deployment. Set `AUTO_CREATE_SCHEMA=true`
only for local development against a disposable database. Add indexes based on actual query patterns.

### Performance indexes

The conversation history paths use these composite indexes:

- `conversations(session_id, updated_at)` for the sidebar's newest-first session listing.
- `messages(conversation_id, created_at, role)` for chronological conversation history.
- `messages(conversation_id, role, created_at)` for bounded user-message profile extraction.

They are created by the Alembic migration `g7h8i9j0k123_add_conversation_query_indexes`.
