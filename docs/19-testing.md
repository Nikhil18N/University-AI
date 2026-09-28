# Testing Strategy

## Unit tests
- Intent routing
- Chunking
- Metadata extraction
- Retrieval filters
- API validation
- Authorization
- Prompt construction

## Integration tests
- API + database
- API + vector DB
- RAG + LLM provider
- Authentication + protected APIs
- Document ingestion pipeline

## AI evaluation
Test:
- greetings
- casual conversation
- university factual questions
- follow-ups
- ambiguous questions
- no-answer cases
- outdated/conflicting documents
- hallucination resistance
- prompt injection
- privacy leakage

Every bug found in production should become a regression test where practical.
