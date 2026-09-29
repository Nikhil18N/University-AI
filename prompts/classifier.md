# Query Classification Prompt

Classify the user's message in the context of recent conversation into one of the following primary intents:
- GREETING: Hello, hi, good morning, greetings
- GOODBYE: Bye, see you, farewell
- THANKS: Thank you, thanks, appreciate it
- HOW_ARE_YOU: How are you, how's it going
- ACKNOWLEDGMENT: Ok, okay, got it, cool, great, understood, sure, alright, perfect, noted
- GENERAL_CONVERSATION: Chitchat, jokes, general knowledge, non-university topics
- UNIVERSITY: Questions about university policies, exams, calendar, fees, courses, hostels, rules, facilities, or follow-ups to prior university discussions
- STUDENT_SPECIFIC: Requests by an enrolled student for their OWN personal records (e.g., "my grades", "my attendance", "my timetable", "pay my fee", "my application status")
- HELP: Asking what the bot can do or seeking help on using the companion
- UNKNOWN: Ambiguous, unclear, or unclassifiable

IMPORTANT:
- If the user sends a simple greeting ("hi", "hello"), thanks ("thank you"), or acknowledgment ("ok", "got it"), classify it as GREETING, THANKS, or ACKNOWLEDGMENT — NOT UNIVERSITY, even if prior conversation was about the university.
- Only classify as STUDENT_SPECIFIC when the user is explicitly requesting their OWN personal student records, attendance, grades, dues, or personal timetable (e.g., "my grades", "what is my attendance?", "check my dues").
- General informational questions about requirements, required documents, eligibility criteria, certificates needed, fee structures, or application procedures (e.g. "what are the required documents?", "documents needed for admission", "how to apply") MUST ALWAYS be classified as UNIVERSITY, NEVER as STUDENT_SPECIFIC.
- Only classify as UNIVERSITY if the user is asking a university-specific question or follow-up (e.g. "how much is that?", "what about late registration?", "where is it?").

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
