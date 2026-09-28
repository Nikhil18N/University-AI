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

Use migrations. Add indexes based on actual query patterns.
