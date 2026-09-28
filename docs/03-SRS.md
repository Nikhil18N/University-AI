# Software Requirements Specification

## 1. Functional scope
The system combines a conversational LLM with a university knowledge retrieval layer.

## 2. Non-functional requirements
### Performance
- Stream responses when supported.
- Keep normal chat responsive.
- Track first-token and total-response latency.

### Reliability
- Graceful degradation when LLM/RAG services fail.
- No silent loss of messages.

### Security
- TLS in production.
- Password hashing if local credentials are used.
- JWT/session security.
- Authorization for student-specific information.
- Secrets stored outside source control.

### Scalability
- Stateless API where practical.
- Background document ingestion.
- Vector DB and relational DB independently scalable.

### Observability
- Structured application logs.
- Metrics for requests, failures, latency, retrieval quality and token/model usage.
