# RAG Specification

## Pipeline

```text
Document
 -> extraction
 -> cleaning
 -> metadata
 -> semantic chunking
 -> embedding
 -> ChromaDB
 -> retrieval
 -> optional reranking
 -> context assembly
 -> LLM
 -> answer + sources
```

## Metadata
At minimum retain:
- document_id
- title
- source
- document_type
- department
- publication_date if known
- effective_date if known
- version
- page number
- ingestion timestamp
- active status

## Retrieval
Start with configurable top-k retrieval. Evaluate several values rather than assuming
one is optimal.

## Grounding
The generation prompt must distinguish:
- user question
- retrieved evidence
- conversation history

The model must not treat conversation history as authoritative university policy.

## No-result behavior
If retrieval confidence/evidence is inadequate:
- Do not invent an answer.
- Ask a clarifying question or say the information could not be verified.
