# Query Classification Prompt

Classify the user's message in the context of recent conversation into one of the following primary intents:
- GREETING: Hello, hi, good morning, greetings
- GOODBYE: Bye, see you, farewell
- THANKS: Thank you, thanks, appreciate it
- HOW_ARE_YOU: How are you, how's it going
- GENERAL_CONVERSATION: Chitchat, jokes, general knowledge, non-university topics
- UNIVERSITY: Questions about university policies, exams, calendar, fees, courses, hostels, rules, facilities, or follow-ups to prior university discussions
- STUDENT_SPECIFIC: Requests for personal student records (e.g., "my grades", "my attendance", "my timetable", "pay my fee")
- HELP: Asking what the bot can do or seeking help on using the companion
- UNKNOWN: Ambiguous, unclear, or unclassifiable

IMPORTANT: If the user is asking a follow-up or clarifying question related to an earlier university topic (e.g. asking "how much is that?", "what about late registration?", "where is it?"), classify it as UNIVERSITY.

Recent Conversation:
{{context}}

User Message:
{{message}}

Respond with valid JSON only, without explanations:
{
  "intent": "INTENT_NAME",
  "confidence": 0.95,
  "needs_clarification": false
}
