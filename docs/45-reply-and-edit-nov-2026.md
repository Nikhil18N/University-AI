# Reply and Edit (v4.17.1, Nov 2026)

## What the student can do

* **Reply** to any saved SRU Buddy answer (the Reply button under it, next to Copy). A preview of that message
  appears above the composer (a fee card shows as "Fee estimate · B.Tech CSE · 30% merit scholarship · ₹2,63,000
  first year"); tap it to jump back to the message, X to cancel. The sent message shows the same quote above it.
* **Edit** their latest **typed** message (the Edit button under it). Buttons tapped after it are allowed: editing
  the marks after choosing the group, concession, hostel and bus still works.

## How it works

1. Every turn has server-generated ids (`done.message_id`, `done.user_message_id`); the browser swaps its
   temporary ids for them, so Reply / Edit always refer to saved messages.
2. **Reply** sends `reply_to`. The server checks the message belongs to the student's conversation
   (`app/services/message_actions.py`), then gives the model that message and, for a fee card, that card's own
   figures as data (`agent._reply_brief`), flagged as the earlier estimate when a newer one exists. Keyword routing
   is skipped for a reply: the model answers about the referenced message.
3. **Edit** sends `edit_of`. Before each typed turn the agent keeps a snapshot of the profile, conversation state and
   history (`memory.save_turn_snapshot`, typed turns only). The server checks the target is the latest typed message,
   puts the snapshot back (`memory.restore_turn_snapshot`), archives the edited message and everything after it
   (`metadata.superseded = true`, never deleted, hidden from the chat and the model's history) and answers the new
   text. The fee engine recalculates from the corrected details.
4. The chat then **replays** the student's later button choices, in order, while each new answer asks the same
   step again (the same option offered, or the same card as when the student chose it). So 870 → 950 out of 1000
   gives the new scholarship slab and the new fee summary without asking again; a choice that no longer applies is
   not replayed.

## Safety

* A message is not editable when that turn or a later one started an admissions request (callback or campus
  visit): editing can't undo it and must not repeat it. The Edit button then explains this instead of opening.
* Edit is disabled while an answer is streaming, while choices are being replayed, while the contact form or the
  welcome-back choice is open.
* A refused reply / edit changes nothing on the server and the chat is put back as it was, with the reason shown.

## Verified (live model, real UI, 390 px widget)

Fee flow with 870/1000 → 25% scholarship, first year ₹2,80,000. Edit to 950/1000 → the four later choices were
replayed and the summary became 30%, ₹2,63,000 (Sem 1 ₹1,44,000, Sem 2 ₹1,19,000), equal to the fee engine.
After a refresh the corrected chat is shown with "Edited" and without 870. A reply to the new fee card was answered
about that ₹2,63,000 estimate. Tests: `backend/tests/test_v4171_reply_and_edit.py` (8).
