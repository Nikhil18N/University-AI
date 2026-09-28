# Security and Authorization

## Roles
- STUDENT
- FACULTY (optional)
- ADMIN

## Rules
- Authentication is required for protected endpoints.
- Authorization is checked server-side.
- A student can only access their own protected data.
- Admin document operations require admin authorization.
- Never expose raw secrets.
- Never log passwords, tokens or API keys.
- Validate uploads and file types.
- Apply request size limits.
- Apply rate limiting.
- Sanitize/validate user input.
- Protect against prompt injection and retrieval-based data leakage.
- Keep student-specific APIs separate from public university knowledge.

## Privacy
Define retention periods before production. Collect only information necessary for
the feature being implemented.
