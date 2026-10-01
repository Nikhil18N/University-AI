# Query Reformulation Prompt

Given the conversation history and a user's follow-up message, rephrase the follow-up message into a complete, standalone search query that can be used for vector retrieval.

Rules:
1. Resolve pronouns (it, that, they, them) and references using the prior conversation context. Preserve the domain topic (e.g., placements, admissions, fees, hostel) when the follow-up asks about attributes or metrics like 'avg ctc', 'cutoff', 'eligibility', 'timings', or 'rules'.
2. Strip out conversational chatter, banter, emotional filler, and greetings (e.g., "haha cool", "lol", "my day was hectic", "btw", "lmao", "thanks bro", "damn", "crazy", "damnn").
3. Expand slang, abbreviations, and informal shortcuts into standard terms (e.g. "wht abt" -> "what about", "elgblty" -> "eligibility", "admsn" -> "admission", "plcmnts" -> "placements", "pakg" / "ctc" -> "placement package CTC", "attndnc" -> "attendance", "hostle" -> "hostel", "schlrshp" -> "scholarship", "mrks" -> "marks").
4. If the message introduces a new topic (e.g. placements, hostel, admissions, transport, labs), keep it focused strictly on that new topic. NEVER combine or blend in previous unrelated topics.
5. Keep the query concise, focused on key university terms (e.g. "SR University B.Tech admission eligibility criteria", "hostel in-time timings for 1st year", "highest placement package company").
6. Do NOT answer the question. Only output the reformulated search query.
7. If the message is just a greeting, acknowledgment, or pure chitchat without any university inquiry, return the original message.

Recent Conversation:
{{conversation}}

User's Follow-up Message:
{{message}}

Standalone Search Query:
