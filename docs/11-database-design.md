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


### v4.15.0: durable conversation state (no schema change)

The structured state of each conversation (open fee step, marks, programme, selections) is also kept in the existing
`user_memories` table, so a student who returns after Redis has expired continues at the same step:

| `memory_key` | `memory_value` |
| --- | --- |
| `cstate.<conversation id>` | `{"__pieces__": n}` (index row) |
| `cstate.<conversation id>#0` … `#n-1` | the state as JSON, in pieces of 240 characters |

Written in the background, one writer per conversation, the latest state always last (`memory._flush_state`);
read on a cache miss (`agent_profile_store.load_conversation_state`). Lead merging: a repeat callback / visit request
from the same mobile number (status `new`, < 7 days, same `metadata.request_type`) updates that `prospective_leads`
row and counts `metadata.repeat_requests` instead of inserting a second row.

## Row Level Security (v4.18.0, migration `j0k1l2m3n456`)

Every table in `public` has Row Level Security enabled with no policies, and the Supabase API roles (`anon`,
`authenticated`) have no privileges on the tables. Supabase's REST API therefore cannot read or change any app data
with the public anon key. The backend connects to Postgres as the table owner, which RLS does not restrict, so the
API works as before. A database event trigger enables RLS on tables created later (where the role may create event
triggers; otherwise a new table's migration must enable it). The migration runs automatically when the API starts.
