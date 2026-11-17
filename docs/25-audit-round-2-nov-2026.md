# 25. Audit round 2 (17 Nov 2026, v2.8.0)

Base: v2.7.0 (commit `121391b`, already merged and live). Prompt version: `2026-11-17.2`.

This round started from the 12-point brief, two chat exports from the live site and the official
fee card PDF (`SRU_FEE_CARD_ADMISSIONS_2027_28.pdf`). It records what was found, what was changed,
what was checked on sru.edu.in, and what still needs a decision from the university.

## 1. What was found

| # | Finding | Root cause | Seen in |
|---|---|---|---|
| 1 | Reopened or exported chats showed answers above their questions | Question and answer were saved in one database transaction, so both had the same timestamp and the order was arbitrary | Chat export 2 |
| 2 | Cards and suggestion buttons disappeared when a chat was reopened | The agent saved only the text of its answer | Reopened chats |
| 3 | After every agent reply the message id became `undefined` | The agent's final event has no `message_id`; several messages shared one React key | Live chat |
| 4 | A new mobile number given in the chat never reached the stored details | Three separate copies (agent memory, browser storage, forms) with no link between them; there was no place to see or edit them | Brief, point 3 |
| 5 | "What will I get on my EAMCET rank 40,000?" was answered from Intermediate marks, then "scholarships are based on Inter %, not rank" (false) | The fee tool returned only the best scholarship, not what each score earns | Chat export 1 |
| 6 | The knowledge file marked "VERIFIED" carried wrong facts: M.Tech ₹1,50,000 (card: ₹1,00,000), M.Sc ₹80,000 / ₹2,00,000 (card: ₹1,00,000), MBA +₹10,000 (card: +₹9,000), PG slabs 10/15/20/25%, and special concessions that do not exist (all girl students, North-East domicile, teachers' children, COVID-affected, partner organisations) | Hand-typed, never checked against the fee card | `09_verified_sru_facts.md` |
| 7 | The fee file listed 20 special concessions; the fee card lists 19 | "Chancellor / Pro-Chancellor recommendation ₹10,000" is not on the 2027-28 card | Fee card PDF |
| 8 | The agent's knowledge needed a Gemini embedding call for every search, and for every chunk when the index was empty | On the free tier the quota runs out: empty index, answers without the handbook, worst in a new chat after a cold start | Brief, point 4 |
| 9 | Edited handbook files never reached the vector index | The index is seeded only when empty, and the repository ships a filled one | `auto_seed.py` |
| 10 | 2 to 3 model calls for one fee question; a model call for "hi" and "thanks"; the same suggestion-button question answered from scratch for every student | No free look-ups before the model, no cache | Agent |
| 11 | When the limit was reached students saw an error, after a wait | No distinction between a per-minute and a per-day limit, no fallback answer | Agent |
| 12 | "Show me a video" could return the first two videos in the file, whatever the topic | Video matching depended on embeddings only | `video_service.py` |
| 13 | Cards said "Call Scheduled", "Campus Tour Confirmed", gave visiting hours 10:00-4:00 (the chat says 9:30-4:30) and a helpline number that is in no official source | Hand-written card text | `Cards.tsx` |
| 14 | Legacy prompts had the same wrong M.Tech / MBA figures and "20 special concessions" | Copies | `prompts/rag.md`, `prompts/system.md` |
| 15 | The legacy chat route had no per-student limit | It also spends Gemini quota | `chat.py` |

## 2. What changed

### Accuracy (brief points 5, 6, 8)
* The fee file was checked line by line against the fee card PDF: all 21 tuition rows and yearly
  increases matched. Corrected: 19 concessions with the card's wording, AC hostel electricity
  deposit ₹10,000, programme names, rankings as printed on the card.
* **The handbook's fee pages are now generated from the fee file**
  (`backend/scripts/handbook_from_fees.py`): all of `08_admissions_fees...md` and sections 3-4 of
  `09_verified_sru_facts.md`. They can no longer drift. Both handbook copies (`data/` and
  `backend/data/`) are kept identical by a test.
* New page `11_official_website_facts_nov2026.md`: what sru.edu.in states (identity, leadership,
  schools, rankings, how to apply, placements, contact) and what no official source states.
* `calculate_fee` now reports what **each** score earns by itself (`scores_considered`), with the
  reason when it earns nothing ("rank-based scholarships cover EAPCET ranks 1 to 20,000 only").
* IB scores 30-37: the fee card's ranges overlap (it says so itself). The lower slab is applied and
  the student is told the Admissions Office confirms.
* The agent is told plainly which things no official source states (documents at admission, refund
  policy, payment dates, cut-off ranks, rules for keeping a scholarship) and must say "the Admissions
  Office confirms this".

### Knowledge that does not depend on AI calls (points 4, 8, 9)
* `backend/app/sru_agent/knowledge.py`: keyword (BM25) search over the handbook files on disk.
  161 passages, ready at start-up, always current, zero API calls. The vector index is used only
  when the keyword search finds nothing (admin-uploaded documents).
* The vector index is refreshed when handbook files change (fingerprint beside the index).

### Gemini free tier (point 9)
| Situation | Model calls before | Now |
|---|---:|---:|
| "hi", "thanks", "how are you", "who are you" | 1 | 0 |
| Fee question with marks ("cse fee with 85%") | 2-3 | 1 |
| Handbook question ("hostel in-time?") | 2 + 1 embedding | 1 |
| Same first question from another student (suggestion buttons) | 1-3 | 0 (saved copy, 6 hours) |
| Callback, visit, cancel, change number | 0-3 | 0 |
| Video lookup | 1 embedding | 0 |

* A per-day limit is recognised: that key rests for an hour and nobody waits for retries.
* When no key is available the student still gets an answer: the fee from the fee file, or the
  matching handbook passage, or a short message saying what still works. Never an error page.
* All model access is in `_KeyRing` and `_generate` in `agent.py`. A paid Gemini plan needs only
  new keys in the environment. Another provider needs a replacement for `_generate` and for the
  tool declarations; nothing else calls the provider.

### Chat consistency (point 2)
* Questions are stamped when asked and answers when finished; ordering also breaks ties by role, so
  **chats saved before this fix are shown in the right order too**.
* Cards and suggestion buttons are saved with the answer and restored on reopening.
* The message id is kept, so React no longer reshuffles messages.
* A chat reopened after a restart or the next day still has its context (read back from the
  database).

### Mobile number and "My details" (point 3)
* One profile per student: `GET / PUT / DELETE /api/v1/agent/profile`, stored in PostgreSQL
  (`user_memories`, keys `agent.*`; no migration).
* New **My details** panel (header 👤 and the phone menu): shows the name and number the chat uses;
  saving changes them everywhere; "Forget my details" removes them.
* In the chat: "change my number to ...", "my new number is ..." update the profile **and** the saved
  callback / visit request (the old number is kept in the lead's `previous_phone`).
* Every agent reply carries the current profile, so the panel is in step at once.
* A number the student already gave is reused for "call me" (the reply names its last four digits).

### Videos (point 7)
* Videos are matched on their own title, category and keywords: relevant, never duplicated, no AI
  call. An unrelated question gets no video.

### Smaller fixes
* Cards: "Callback Requested" / "Campus Visit Requested", one set of visiting hours, official helpline.
* Legacy chat route limited to 20 messages a minute per student.
* Network failures to Google are treated like a busy server (retry, then a fallback answer).
* Expected limit situations write one log line instead of a stack trace.

## 3. Checked on the official website (17 Nov 2026)

Pages read: `/about`, `/admission/`, `/placements/`, `/fee-scholarship/`,
`/academics/program/` (undergraduate pages 1, 2 and 4; postgraduate page 1) and `/programs-2026`.
Not read: individual department, hostel, international and research pages; `/programs` did not load.

| Topic | Website | Project sources | What the agent says |
|---|---|---|---|
| Chancellor, Pro-Chancellor, VC, Registrar | As in the handbook | Same | Same |
| Parent body | Sri Rajeshwara Educational Society, 185 institutions (95 in another paragraph of the same page) | 185 | 185 |
| Campus | 170 acres | 170 | 170 |
| NIRF 2025, NBA Tier-I, ICAR, THE 801-1000 | Same | Fee card agrees | Same |
| Hostel fees | ₹1,15,000 / 1,25,000 / 1,25,000 / 1,35,000 | Same | Same |
| **Minimum marks** | B.Tech 60% in PCM plus JEE Main / state entrance; B.Sc, B.Des, M.Sc, MBA 55%; BBA, B.Com 50%; BCA, MCA 60% (pages are for 2026-27) | Fee card: standard fee from 50% (55% CSE/ECE) | Fee card (2027-28) |
| **Average package** | 6.5 LPA | 6 LPA (Oct 2026 presentation) | 6 LPA |
| **Top offers** | 51 LPA; Amazon 45; ServiceNow 44 (2025) | 51 Microsoft (2025); 46.38 Amazon (2026); 49.30 ServiceNow (2027) | Presentation |
| **Fee page** | Still 2026-27: admission fee ₹25,000, concessions in %, AC electricity deposit ₹5,000 | Fee card 2027-28 | Fee card |
| WhatsApp | +91 8331004040 in text, a different number in the link | 8331003030 / 8331004040 | 8331003030 |
| Documents at admission, refund policy, dates | Not stated | Not stated | "The Admissions Office confirms this" |

## 4. Please decide / confirm

1. **Minimum marks for 2027-28** for each programme (fee card 50% / 55% against the website's 60% / 55%).
2. Average package: 6 or 6.5 LPA; and which top offers to quote.
3. Campus visit hours (9:30 AM to 4:30 PM is used; no official source states them).
4. Examination fee after the first year (the card says "Examination Fee (First Year) ₹5,000").
5. Which programmes pay the ₹30,000 specialisation fee.
6. IB slabs for scores 30 to 37.
7. Early-bird ₹550 application offer (still shown in an advertisement card; not on the fee card).
8. Give the students the official list of **documents required at admission** and the **refund
   policy**, to be added as a handbook page.
9. Ask the web team to update the fee and programme pages on sru.edu.in to 2027-28.

## 5. Deploying

1. Merge (see `READ_ME_FIRST.md` in the delivery zip). No database migration.
2. Backend: nothing new is required. Optional settings are at the end of `backend/.env.example`.
3. After the first start the log shows `Handbook keyword index ready: 161 passages`.
4. Check on the live site: "hi" (instant), "cse fee with 85%", "in eamcet I got 40000 rank, what
   scholarship?", "ask someone to call me" then a name and number, "change my number to ...", open
   **My details**, reload and reopen the chat.

## 6. Tests

| Command | Result on 17 Nov 2026 |
|---|---|
| `cd backend && pytest` with PostgreSQL | 467 passed, 1 skipped (431 before this round) |
| `cd backend && pytest` without a database | 459 passed, 7 skipped, 2 failed (those 9 need PostgreSQL) |
| `cd frontend && npm test` | 3,477 checks, calculator equal to the backend for 338 inputs |
| `cd frontend && npm run build` | passes |

Browser run on the built site against the real backend code and a local PostgreSQL (a stand-in
replaced Gemini): greeting, fee question through the verification form, callback, number change in
chat, My details (shows the new number; a change there updates the saved lead), reload and reopen
(identical order, cards and buttons), phone 390 px and tablet 820 px (no horizontal overflow),
and the three replies when the model is unavailable.

**Not tested:** a live Gemini call, the production database, and real phones. There are no user
accounts in this project (a student is identified by the browser), so registration, login and
logout do not exist to be tested; details persist per browser, not across devices.

Changed tests (behaviour changed on purpose): two tests used "hello" as a filler message and now
use a real question, because greetings no longer call the model; two video tests now expect
videos chosen by topic from the real catalogue instead of a mocked embedding result.
