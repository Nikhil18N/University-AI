# SRU Buddy — Final Production Readiness Report (released as v4.18.0, 26 Nov 2026)

## Release 4.18.0 (PRs #37, #38, #39 and the version bump)

* Reply to any answer or fee card; Edit the latest typed message (recalculates, keeps later choices).
* Fee cards shared as real PNG images (Download / Copy fallbacks).
* Guided eligibility / scholarship check from any wording or a "Yes": board first, marks out of that board's total.
* A "Yes" to the bot's callback offer saves the callback on the number on file.
* Admissions leadership answered from the official FAQ again (knowledge index repaired; better re-ranking).
* Every chat turn is saved even if telemetry fails; database migrations are applied when the API starts.
* Smaller Edit button.

Work in progress during the mission was labelled "v4.17.1" in code comments and in the sections below.

Mission: accuracy, model-first understanding, verified retrieval, fee-card sharing, Reply / Edit, memory, and a full
rehearsal of the 20-step demo. This report covers what was done, how it was verified, and what is still open.

## 1. Commits

| | |
|---|---|
| Baseline (main at the start) | `556715c` (v4.17.0) |
| Main during the mission | `6340341` (PR #36 by Mahesh-ch06: merged commits 1-3 below), then `2137184` (Nikhil Nakka, Phases 1-4, `5009cdf`), then `23589a2` (Nikhil Nakka: observability, multi-query, model tiering, structured flows, `4403e96`) |
| Branch | `claude/great-ptolemy-1x1q7k` |
| Commits | `2fde644` accuracy · `fb6f8d4` model-first, honest errors, sources, outdated cards · `54c65af` PNG sharing · `5f96de9` Reply / Edit · `2cda021` merge of main + integration fixes · `4ecbbba` knowledge index repair · `52b9838` this report · `8a66582` merge of the latest main · retrieval follow-up fixes (below) |

## 2. Root causes found

1. **The admissions leader could not be named.** The DOCX parser treated every Heading paragraph as a section label,
   so all 113 Heading-3 questions were lost, including Leadership Q16 "Who is the Senior Director of Admissions and
   Marketing?". Retrieval also stopped at the first keyword hit, and the faculty search matched the word "Director" to
   unrelated people.
2. **The same defect came back on main after Phases 1-4.** The vector index committed in `5009cdf` had no vector for
   any of the 187 FAQ chunks ("Error finding id"; keyword-only fallback, which does not cover the FAQ). Live, "Who
   leads admissions at SRU?" was answered "not listed in the official records". Cause: index segment files (normally
   git-ignored) committed from a different moment than `chroma.sqlite3`.
3. **Similar names were treated as the same person.** No identity rules (full name + exact designation), and no
   re-check when the student challenged an answer.
4. **Workflow interruptions were decided by message length.** A short typed question during a step was taken as the
   step's answer.
5. **Silent legacy fallback.** A failed `/agent/stream` turn was re-sent to `/chat/stream` (no state, processed twice).
6. **Sensitive details streamed before the self-check** (amounts, names, roles could flash and then change).
7. **Sources were not saved or passed to the chat bubble.** The `feeOutdated` flag was missing from the bubble's
   memo comparator, so outdated fee cards were not re-marked.
8. **Sharing sent text only** (wa.me links; no image).
9. **No stable message ids or state snapshots**, so Reply / Edit could not be done properly.
10. **"Who leads admissions at SRU?" still missed the answer on the latest main.** The Leadership FAQ is 4th by
    vector distance (0.293 vs 0.282-0.287 for general admissions FAQs) and the new RRF merge keeps 6 passages, so it
    was cut. The question-word re-rank used 5-letter stems ("leads" vs "leade(rship)") and could not lift it. Also,
    a follow-up ("Are you sure?") only had the general search tool, not the tool that produced the answer.
11. **After the merge, memory lost turns.** `memory.warm_turn_keys` (Phases 1-4) overwrote newer in-process values
    with older Redis copies: history turns and saved details disappeared. Three existing tests failed on main as well.

## 3. What changed, and why

| Area | Files | Why |
|---|---|---|
| DOCX parsing and additive import | `scripts/parse_university_docx.py`, `scripts/ingest_university_doc.py`, `services/auto_seed.py` | Question-shaped and numbered headings, multi-paragraph answers, bold inside answers, URLs kept, unanswered and orphan paragraphs reported; additive index (add first, then remove superseded); retired fee text excluded |
| People and offices | `sru_agent/faculty.py`, `sru_agent/tools.py`, `sru_agent/answer_check.py`, `sru_agent/prompt.py` | Identity vs role, exact / partial / ambiguous matches, offices outside the directory answered from approved knowledge, challenge re-checks, unverifiable names replaced |
| Retrieval | `app/main.py` (`agent_knowledge_search`) | Keyword and vector evidence together, distance cut, re-rank by question words, sources kept |
| Streaming and sources | `sru_agent/agent.py`, `app/main.py`, `services/conversation_service.py` | Hold at the first sensitive detail, self-check, then release; answer sources saved and returned |
| Model-first | `sru_agent/agent.py`, `frontend/src/pages/ChatPage.tsx`, `services/api.ts` | A typed message continues a step only if it gives what the step asked for; held messages keep their typed / button source; no silent legacy fallback |
| Fee cards | `utils/feeCardImage.ts`, `components/FeePlanCards.tsx`, `public/widget.js` | Real PNG (canvas), native file share, Download / Copy caption / Copy image fallbacks, truthful status |
| Reply / Edit | `services/message_actions.py`, `sru_agent/router.py`, `sru_agent/memory.py`, `schemas/chat.py`, `utils/messageActions.ts`, `MessageBubble.tsx`, `ChatPage.tsx` | Server message ids, ownership checks, typed-turn snapshots, archive (never delete), replay of later choices |
| Merge integration | `sru_agent/agent.py`, `sru_agent/memory.py`, `main.py`, `router.py` | Reply kept through the new prompt structure; replies never served from the FAQ cache; stale cache overwrite fixed; message ids and telemetry both logged |
| Retrieval follow-up | `app/main.py` (`_rerank_by_question_words`), `sru_agent/tools.py`, `sru_agent/agent.py` | 4-letter stems in the re-rank ("leads" matches "Leadership"); the previous answer's read-only tools stay available on the next turn (actions never carried over) |
| Knowledge index | `chroma_data/chroma.sqlite3`, `scripts/repair_vector_index.py` | 187 missing vectors restored; whole index re-materialised consistently; reusable check / fix tool |
| Docs | `docs/12`, `docs/45`, this report | API contract (reply_to, edit_of, ids, message fields), behaviour, report |

## 4. Contributor changes preserved

* **Dinesh Karupothula** (`4a7d00c`, `8ea827e`, `6349b0c`, `416e50c`, `47576dd`, `772beef`): board-first fee flow
  (board and stage before marks), dynamic maximum marks, rejection of impossible marks, reuse of saved details. Kept
  and verified live ("1200 is more than the maximum of 1000").
* **PRs #33-#35** (agent merge, model-first architecture): kept.
* **Mahesh-ch06** (PR #36): kept.
* **Nikhil Nakka** (`5009cdf`, Phases 1-4): kept in full (telemetry and migrations, prompt split, tool pruning, FAQ
  cache, llm_loop / tool_runner / fee_coordinator / postprocess, Redis-backed settings and cards, removal of the
  Verified Sources drawer). Only integration fixes were added: replies excluded from the FAQ cache, the stale cache
  overwrite fixed, the vector index repaired.

## 5. Admissions source

`backend/data/SRU Agentic AI.docx` → Leadership, Q16 "Who is the Senior Director of Admissions and Marketing?" (Heading 3
paragraph 609, answer paragraph 610) → chunk "University FAQ — Leadership": **Dr. Ram Raghotham Rao Deshmukh, Senior
Director of Admissions and Marketing.** Dr. Rupesh Mishra: Associate Professor and Director of Centre for Experiential
Learning, Computer Science & AI (`faculty_directory.json`); Boys Hostel Warden (handbook 01 and 09). No answer is
hard-coded; both come from retrieval.

## 6. DOCX recovery and indexing

* Entries: 78 → 191 (114 recovered; 1 earlier entry, "m.tech, m.sc and agriculture?", has no answer and is not
  indexed); 93 questions without an answer and 18 orphan paragraphs reported, nothing dropped silently.
* Index: 187 FAQ chunks, no duplicates after two runs, "University FAQ — Fee" excluded (the fee engine is the single
  source). The whole knowledge DB was never cleared.
* Repair (this session): 331/331 chunks with a vector (was 144/331 on main), videos 75/75 with identical ranking,
  exemplars 3/3. "Who is the Director of Admissions?" → Leadership FAQ first.

## 7. Fee amounts before and after Edit (B.Tech CSE, TSBIE, completed, MPC, no concession, no hostel, no bus)

| | Marks | Scholarship | First year | Sem 1 | Sem 2 | Full course |
|---|---|---|---|---|---|---|
| Before edit | 870/1000 (87%) | 25% | ₹2,80,000 | ₹1,52,500 | ₹1,27,500 | ₹11,44,000 |
| After edit | 950/1000 (95%) | 30% | ₹2,63,000 | ₹1,44,000 | ₹1,19,000 | ₹10,76,000 |

Both equal the fee engine (the same calculator the 3,794 frontend checks compare against).

## 8. PNG sharing and link check

* Fee summary PNG, 1080 px wide, 229,916 bytes: SRU branding, programme, year, scholarship, confirmed payable,
  semester table, notes, disclaimer; no phone numbers, conversation ids or chat text; amounts taken from the card.
* Native file share (mocked `navigator.share`): received `image/png` + the caption verbatim with the calculator link.
  No file sharing: options panel, Download worked. Cancel: quiet. WhatsApp-to-admissions is separate.
* `https://sru.edu.in/fee-scholarship/` in a fresh browser session: HTTP 200, Scholarship Calculator visible
  (Program, Board / Entrance, Marks / Rank, Calculate).

## 9. Tests

* Backend: **1,796 passed, 1 skipped**; 1 deselected (`test_feedback_submission`, needs a real Gemini key, failing
  before this work).
* Frontend: TypeScript clean, production build OK, fee calculator 3,794 checks (338 backend answers compared),
  effects 11 checks, oxlint 0 errors (warnings were there before).
* Test types: unit and integration tests use fake models (deterministic). Live checks below use the real Gemini model
  through the local review server on the merged code. No real phone or tablet was used.

## 10. Live rehearsal of the 20-step demo (real model, real UI at 390 px)

| Step | Result |
|---|---|
| 1-2 Who leads admissions; source and designation | Dr. Ram Raghotham Rao Deshmukh, Senior Director of Admissions and Marketing (3 of 3 fresh chats on the final code); source "University FAQ — Leadership" |
| 3-4 "Rupesh Mitra" challenge; "Are you sure?" | Not agreed; evidence re-checked; supported answer kept |
| 5 Dr. Rupesh Mishra's role | Associate Professor, Director of Centre for Experiential Learning; Boys Hostel Warden |
| 6-7 Scholarship flow: programme, board, stage | Board-first flow, step cards |
| 8-10 "placement record" mid-flow, resume | Relevant placement answer; flow resumed at the marks step (API-level run) |
| 11 Marks and estimate | 870/1000 → 25%, ₹2,80,000 |
| 12-13 Edit marks; verify | 950/1000 → 30%, ₹2,63,000, later choices replayed; equals the engine |
| 14 Refresh | Corrected chat persists, "Edited", 870 gone |
| 15-16 Reply to the new fee card | Reply bar names the ₹2,63,000 estimate; answer explains that estimate |
| 17 Share PNG | Real PNG produced and shared (mocked share sheet) / downloaded |
| 18 Calculator link, fresh session | Works |
| 19 Continue / Start fresh | Continue restores and remembers 30% (edited marks); Start fresh is a new session that knows nothing |
| 20 No duplicate leads | Callback asked twice → 1 lead ("already registered") |
| Extra | Impossible marks rejected; API failure shows an honest error, no fallback; missing evidence stated; unseen phrasing ("big boss of admissions") answered; helplines 833 100 3030 and 833 100 4040 correct |

## 11. Status of every item

| Item | Status |
|---|---|
| Audit, contributor review, baseline | Implemented and verified |
| DOCX parsing and additive re-index | Implemented and verified |
| Entity resolution, challenge handling | Implemented and verified (live) |
| Hybrid retrieval, sensitive-claim buffering | Implemented and verified |
| Model-first interruptions, frontend interception, no legacy fallback | Implemented and verified |
| Sources pipeline (document → retrieval → answer → API → saved) | Implemented and verified; the chat-bubble display was removed on main by `5009cdf` (contributor decision kept) |
| `feeOutdated` comparator | Implemented and verified |
| Fee engine protection, board-first flow | Existing functionality preserved |
| PNG sharing | Implemented and verified in Chromium; **not verified on a real device** |
| Reply / Edit | Implemented and verified (live, UI) |
| Memory: Continue / Start fresh | Existing functionality preserved and verified; stale-cache bug from the merge fixed |
| Helplines | Verified |
| Knowledge index repair | Implemented and verified |
| Real-device testing | Deferred (no device available) |
| Large-scale simulation in this mission | Not run (not claimed) |

## 12. Limitations and open points

0. **Known model issue:** after "What role does Dr. Rupesh Mishra hold?" (answered correctly from the faculty
   directory), the follow-up "Are you sure? Please verify that again." can make the model re-check with the general
   search only, find his Boys Hostel Warden record, and wrongly withdraw his directory designation (seen in most live
   runs on the final code; he holds both roles). The scripted demo order (steps 1-5) is not affected. Next step: a
   check that blocks withdrawing a claim that the previous turn's official records support.

1. Share sheets on real iOS / Android devices are untested.
2. The "Verified Sources" drawer was removed from the chat bubble on main (`5009cdf`). Sources are still produced,
   saved and returned by the API. Restoring the display is a one-component change if the team wants it.
3. Tool pruning (`select_tools_for_message`, `5009cdf`) picks tools by keywords. Leadership questions get only the
   general search tool; they are answered correctly now through the repaired FAQ index. The `dr\.?\s+[a-z]\b`
   pattern never matches a full name ("Dr. Rupesh"). Recommended for review by its author; not changed here.
4. Data conflict for the owners to settle: breakfast 7:15–8:45 AM (FAQ) vs 7:30–8:30 AM (approved facts).
5. Edit replays a later choice only when the new answer asks the same step; otherwise the student answers again.
6. The helpline answer shows "Counsellors available: Mon–Sun, 00:00–23:59" from the admin settings; check the hours.

## 13. Deploy

1. Open a pull request `claude/great-ptolemy-1x1q7k` → `main`; review; merge (main deploys the backend and frontend).
2. Backend: `alembic upgrade head` (the two Phases 1-4 migrations, if not applied yet).
3. Set `RAG_CACHE_VERSION=2` (or delete the `sru:faq:*` Redis keys) so no answer cached while the index was broken is
   served.
4. In the backend shell: `python scripts/repair_vector_index.py` → expect "331 with a vector, 0 without". If production
   keeps its own Chroma directory instead of the repository copy, run it there with `--fix`.
5. Smoke test: the five admissions questions, one fee flow with an edit, Continue / Start fresh.

## 14. Rollback

* Code: `git revert -m 1 <merge commit>` on main and redeploy, or redeploy the previous build (`2137184`) from the
  hosting dashboards.
* Data: nothing destructive was done. Edits only flag messages (`metadata.superseded`); the previous index is in git
  history; no records, leads, conversations or knowledge documents were deleted.

## 15. Ready to demo

* Admissions leadership questions, including the wrong-name challenge and "Are you sure?"
* The scholarship flow with an off-topic question in the middle, and impossible marks rejected
* Editing the marks and seeing the estimate recalculate (25% → 30%, ₹2,80,000 → ₹2,63,000)
* Replying to a fee card and getting an answer about that exact estimate
* Sharing the fee card as a PNG (show Download on a laptop; native share on a phone is untested)
* The official calculator link
* Continue / Start fresh for a returning student
* Callback requests without duplicates
