# AI Coding Agent Rules

You are implementing the University AI Companion.

## Non-negotiable rules
1. Read the relevant documents in `docs/` before changing architecture or behavior.
2. Do not change the core technology stack without explicit approval.
3. Keep the LLM behind a provider interface so local and cloud models can be swapped.
4. Never hardcode API keys, passwords, JWT secrets, or database credentials.
5. Never invent university facts. University-specific answers must be grounded in retrieved sources.
6. If retrieval has insufficient evidence, clearly state that the information could not be verified.
7. Keep business logic out of API route handlers.
8. Use typed request/response schemas.
9. Add tests for new backend functionality.
10. Update API/database documentation when contracts or schemas change.
11. Do not silently change database schemas. Create a migration.
12. Do not add dependencies without explaining their purpose.
13. Keep prompts versioned under `prompts/`.
14. Never expose system prompts, internal tool details, secrets, or private student data.
15. Apply authentication and authorization to student-specific data.
16. Prefer small, reviewable changes over large rewrites.
17. Run relevant tests/lint/type checks before declaring a task complete.
18. Do not delete working functionality to make a new feature pass.
19. Preserve source metadata through the entire RAG pipeline.
20. Every RAG answer should be capable of returning source references.

## Development workflow
1. Inspect the relevant docs.
2. Identify affected components.
3. State the implementation plan.
4. Implement the smallest complete change.
5. Test it.
6. Update documentation if behavior changed.
