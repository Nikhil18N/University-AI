# Query Reformulation Prompt

Given the conversation history and a user's follow-up message, rephrase the follow-up message into a complete, standalone search query that can be used for vector retrieval.

Rules:
1. Resolve pronouns (it, that, they, them), references, affirmative confirmations (e.g. if the assistant asks "Would you like to know more about X or Y?" and the user says "yes", "sure", or "tell me more", reformulate into a search query for X and Y details), and student follow-up answers using the prior conversation context (e.g. if the user previously discussed admissions and then says "im interested in B.Tech CSE", reformulate into "SR University B.Tech CSE admission eligibility criteria and requirements"). Preserve the domain topic (e.g., admissions, placements, fees, hostel) when the follow-up provides answers, attributes, or metrics. NEVER invent or introduce numbers, percentages, or grades that were not explicitly mentioned by the user.
2. Strip out conversational chatter, banter, emotional filler, and greetings (e.g., "haha cool", "lol", "my day was hectic", "btw", "lmao", "thanks bro", "damn", "crazy", "damnn").
3. Fix all typos, spelling mistakes, and informal abbreviations into standard terms (e.g. "wht abt" -> "what about", "elgblty" -> "eligibility", "admsn" -> "admission", "plcmnts" -> "placements", "pakg" / "ctc" -> "placement package CTC", "attndnc" -> "attendance", "hostle" -> "hostel", "schlrshp" -> "scholarship", "mrks" -> "marks", "clg" -> "college", "bteck" -> "B.Tech").
4. Translate student colloquialisms and commercial synonyms into official university handbook terminology:
   - "discount" / "fee waiver" / "concession" -> "scholarship and fee concession"
   - "dorm" / "room" / "quarters" -> "hostel accommodation"
   - "salary" / "job package" -> "placement package CTC"
   - "seat" / "join" -> "admission eligibility criteria"
5. If the message introduces a new topic (e.g. placements, hostel, admissions, transport, labs), keep it focused strictly on that new topic. NEVER combine or blend in previous unrelated topics.
6. Keep the query concise, focused on key university terms (e.g. "SR University B.Tech admission eligibility criteria", "hostel in-time timings for 1st year", "highest placement package company").
7. Do NOT answer the question. Only output the reformulated search query.
8. If the message is just a greeting, acknowledgment, or pure chitchat without any university inquiry, return the original message.

Recent Conversation:
{{conversation}}

User's Follow-up Message:
{{message}}

Standalone Search Query:
