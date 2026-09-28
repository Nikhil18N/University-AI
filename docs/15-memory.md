# Conversation Memory

## Short-term memory
Store enough recent conversation history to resolve references and maintain continuity.

## Long-term memory
Only store explicitly permitted, useful, non-sensitive preferences or profile data.
Define retention and deletion behavior before production.

## Memory safety
- Never use memory as authorization.
- Never infer sensitive personal attributes.
- User-specific university data must come from authorized systems.
- Allow users to clear conversation history according to the product's privacy design.

## Context strategy
Use a bounded recent-message window plus optional summaries rather than sending an
unbounded conversation to the LLM.
