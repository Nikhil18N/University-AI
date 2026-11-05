# Admin Dashboard

## Documents
- Upload
- Validate
- Process
- Reindex
- Activate/deactivate
- View metadata
- View ingestion errors

## Operations
- View service health
- View ingestion jobs
- View feedback
- View aggregate usage/latency

## Conversation Audit & Model Improvement
- View all user chat conversations with search, pagination, and feedback filtering (All / 👍 Positive / 👎 Negative / None)
- Inspect full conversation dialogue threads including user questions, AI responses, model metadata, and retrieved source citations
- Promote verified, high-quality question-and-answer pairs directly into ChromaDB `verified_exemplars` collection to dynamically boost model accuracy and retrieval performance
- Export conversation logs for offline fine-tuning and benchmark evaluation
- Prune/delete test or spam conversations

Access to user conversations requires authorization via `X-Admin-Key`.

