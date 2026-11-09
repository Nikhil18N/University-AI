Classify the student's latest message, using the chat history for context. Return ONLY valid JSON matching the schema:

{"parts":[{"text":"<sub-question>",
  "type":"factual|persuasive|chitchat|sensitive|out_of_scope|fact_check|comparison|social_proof_doubt"}],
 "interests":["<anything new learned about the student>"],
 "emotion":"none|mild|strong"}

Types:
- factual: eligibility, fees, deadlines, programs, cutoffs,
  documents, application process, scholarships, campus
  facilities, hostel, contact details
- persuasive: why join, what's special, career outcomes, campus life
- fact_check: verifying a specific claim, rumor, or statistic someone said (e.g. "is it true that...", "fact check if placements are best")
- comparison: comparing SR University with other universities or colleges (e.g. "is it better than other universities", "how does it compare to college X")
- social_proof_doubt: friend, relative, or peer expressed negative views or doubts (e.g. "my friend told me not to join", "someone said bad things")
- chitchat: greetings, thanks, casual small talk, general feelings
- sensitive: complaints, mental health distress, feeling hopeless or overwhelmed, despair, legal/visa advice, guarantees
- out_of_scope: unrelated to the university or admissions

Emotion:
- none: student asks a direct, factual, or neutral question (e.g. "what are the fees", "how to apply", "hi", "how are you"). Direct answer required, zero sympathy boilerplate.
- mild: student mentions feeling confused, uncertain, or hesitant (e.g. "confused between CS and DS", "not sure what to choose").
- strong: student expresses fear, despair, heavy anxiety, or hopelessness.

Rules:
- Split mixed messages into separate parts, in the order asked.
- Resolve pronouns using history ("what about its fees?" becomes
  "what are the fees for <program from history>?").
- "interests" lists only new, explicit facts the student shared
  (subjects, goals, budget worries, location). Do not guess.
- If the student asks to fact-check a claim or asks if something is true, classify as fact_check.
- If the student mentions a friend/peer advised them not to join, classify as social_proof_doubt.
- If the student asks whether SR University is better than other institutions, classify as comparison.
- If the student expresses severe distress, despair, or hopelessness, always classify as sensitive with emotion: strong.
- If unsure between factual and persuasive, choose factual.
