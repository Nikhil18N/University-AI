# Query Reformulation Prompt

Given the conversation history and a user's follow-up message, rephrase the follow-up message into a complete, standalone search query that can be used for vector retrieval.

Rules:
1. Resolve pronouns (it, that, they, them) and references using the prior conversation context.
2. If the message is already a standalone question, keep it unchanged.
3. Keep the query concise, focused on key university terms (e.g. "exam registration late fee", "hostel curfew timings").
4. Do NOT answer the question. Only output the reformulated search query.
5. If the message is just a greeting or chitchat, return the original message.

Recent Conversation:
{{conversation}}

User's Follow-up Message:
{{message}}

Standalone Search Query:
