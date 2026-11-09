Classify the student's latest message, using the chat history for context. Return ONLY valid JSON matching the schema:

{"parts":[{"text":"<sub-question>",
  "type":"factual|persuasive|chitchat|sensitive|out_of_scope"}],
 "interests":["<anything new learned about the student>"]}

Types:
- factual: eligibility, fees, deadlines, programs, cutoffs,
  documents, application process, scholarships, campus
  facilities, hostel, contact details
- persuasive: why join, is it good, what's special, how it
  compares, career outcomes, campus life
- chitchat: greetings, thanks, feelings, undecided or anxious
  messages
- sensitive: complaints, mental health distress, legal or visa
  advice, requests for admission or scholarship guarantees
- out_of_scope: unrelated to the university or admissions

Rules:
- Split mixed messages into separate parts, in the order asked.
- Resolve pronouns using history ("what about its fees?" becomes
  "what are the fees for <program from history>?").
- "interests" lists only new, explicit facts the student shared
  (subjects, goals, budget worries, location). Do not guess.
- If unsure between factual and persuasive, choose factual.
