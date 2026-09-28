# Query Reformulation Prompt

Given the conversation history and a user's follow-up message, rephrase the follow-up message into a complete, standalone search query that can be used for vector retrieval.

Rules:
1. Resolve pronouns (it, that, they, them) and references using the prior conversation context.
2. If the message is already a standalone question or introduces a new topic (e.g. placements, hostel, admissions, transport, labs), keep it focused strictly on that new topic. NEVER combine or blend in previous unrelated topics.
3. Keep the query concise, focused on key university terms (e.g. "exam registration late fee", "hostel curfew timings", "campus placements").
4. Do NOT answer the question. Only output the reformulated search query.
5. If the message is just a greeting, acknowledgment, or chitchat, return the original message.

Recent Conversation:
{{conversation}}

User's Follow-up Message:
{{message}}

Standalone Search Query:
