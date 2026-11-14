# Query Reformulation Prompt (v3)

Given the conversation history and a user's follow-up message, rephrase the follow-up message into a complete, standalone search query usable for vector retrieval against SR University's official knowledge base.

## Rules

1. **Resolve references and context.** Resolve pronouns (it, that, they, them), anaphoric references, affirmative confirmations (e.g. if the assistant asks "Would you like to know about X or Y?" and the user says "yes", "sure", or "tell me more", reformulate into a query for X and Y details), and student follow-up answers using the prior conversation context. NEVER invent or introduce numbers, percentages, or grades not explicitly mentioned by the user.

2. **Strip conversational filler.** Remove greetings, chatter, banter, emotional filler, and informal markers — including:
   - English slang: "btw", "lol", "lmao", "haha", "tbh", "bro", "dude", "omg", "ngl", "idk", "smh", "literally", "basically"
   - Hinglish / Telugu-English: "yaar", "bhai", "anna", "andi", "ayya", "kya", "nenu", "meeru", "oka", "cheppandi", "cheppu", "konchem", "kaadu", "ledu", "ayyindi", "avutundi"

3. **Fix spelling mistakes and shorthand.** Correct ALL typos and informal abbreviations into standard English:
   - "elgblty / eligiblity / eligble" → "eligibility"
   - "admsn / admision" → "admission"
   - "plcmnt / placmnt" → "placement"
   - "hostle / hostal" → "hostel"
   - "attndnc / attendence" → "attendance"
   - "schlrshp / scholrshp / scolarship" → "scholarship"
   - "mrks" → "marks", "clg / collge / cllg" → "college", "bteck / btech" → "B.Tech"
   - "syllubus / syllbus / silabus" → "syllabus"
   - "semister / semster" → "semester"
   - "libary" → "library", "faculity" → "faculty", "aplication" → "application"
   - Informal short forms: "wht" → "what", "abt" → "about", "pls / plz" → "please", "u" → "you", "ur" → "your", "r" → "are", "2" → "to"

4. **Translate informal / colloquial vocabulary to official university terminology:**
   - "discount / concession / fee waiver / fee help / financial help" → "scholarship and fee concession"
   - "dorm / room / quarters / pg / paying guest / stay" → "hostel accommodation"
   - "salary / job package / avg salary / highest salary" → "placement package CTC"
   - "seat / join / getting in / take admission" → "admission eligibility criteria"
   - "company / companies / mnc / hire / hiring" → "placement recruiter"
   - "cost / price / charges / how much fees" → "fee structure"
   - "last date / last day" → "application deadline"
   - "cut off / cutoff marks" → "admission cutoff percentage"
   - "jobs / work" → "placement"
   - "stay / room / quarters" → "hostel accommodation"
   - "pass marks / pass percentage" → "minimum passing marks"
   - Hinglish meaning: "chahiye" → "required", "kitna / kitne" → "how many / how much", "kab" → "when", "kahan" → "where", "kaise / kaisa" → "how"

5. **Handle new topics correctly.** If the message introduces a new standalone topic (placements, hostel, admissions, transport, labs, scholarships), keep the query focused strictly on that new topic. Do NOT blend in previous unrelated topics.

6. **Keep the output query concise and search-optimised.** Use specific university-domain terms (e.g. "SR University B.Tech admission eligibility criteria", "hostel in-time timings for 1st year students", "scholarship merit fee waiver eligibility", "highest placement package CTC 2024").

7. **Do NOT answer the question.** Only output the reformulated search query — nothing else.

8. **If the message is pure greeting / acknowledgment / chitchat with no university topic**, return the original message unchanged.

---

Recent Conversation:
{{conversation}}

User's Follow-up Message:
{{message}}

Standalone Search Query:
