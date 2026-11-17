# 27. Admissions brief: fees, faculty, widget, visits and speed (17 Nov 2026, v3.0.0)

Base: v2.9.0 (commit `3665fe3`). The free Gemini API is unchanged. The 2027-28 fee card PDF is
still the only source for fees (the copy attached to this brief is identical to the one already
in use).

## 1. Summary

| # | Brief item | What SRU Buddy does now |
|---|---|---|
| 1 | Fee enquiry and scholarship calculation | Before a personal fee it checks programme and branch, board, marks and (for B.Tech / B.Sc Agriculture) JEE Main / EAPCET. Missing items are asked in one short message, without an AI call. Then it calculates from the fee card and points to the official calculator |
| 2 | Relevant follow-up suggestions | New topic-based chips (`sru_agent/followups.py`) that follow the question and the tool that answered it, and never repeat the question |
| 3 | Faculty profiles | All 340 profiles from sru.edu.in/faculty in a searchable file, a `find_faculty` tool and a faculty card. Covers deans, heads, names, departments, research areas and subjects |
| 4 | SRU strengths | A sourced "Why SRU" block (rankings, placements, scholarships, industry, international, research, faculty), used where relevant and worded freshly each time |
| 5 | Answer formatting | Bullets for lists of facts or steps, short paragraphs for "why / how" questions, one or two sentences for simple facts, at most 150 words |
| 6 | Widget version | `widget.js`: one script line adds a chat bubble to any page. It opens the same app in compact mode, so both versions always share the knowledge, fixes and AI |
| 7 | Campus visits | Never booked or confirmed. SRU Buddy gives the admissions contacts from sru.edu.in/visit-us and can pass the student's number on as a callback request ("not a booking") |
| 8 | Latency | Found and fixed: about 3-4 seconds of every reply were database / cache trips. Answers now stream as Gemini writes them, and the prompt is 23% shorter |

## 2. Fee enquiries (item 1)

`backend/app/sru_agent/fee_intake.py` runs before the AI for every fee question:

| Student writes | SRU Buddy |
|---|---|
| "What is the fee?" | Asks which programme (and branch for B.Tech) |
| "B.Tech fees" | Lists the 2027-28 standard tuition of every B.Tech branch and asks which one |
| "CSE fee" | Gives the standard tuition, then asks in ONE message: board, Intermediate / 12th marks, JEE Main percentile or EAPCET rank |
| "CSE fee with 96%" | Asks the board, because 96% is 30% for State Board but 40% for CBSE / ICSE. The board is only asked when it changes the answer |
| "CSE fee with 85%" | Asks once about JEE Main / EAPCET, because a good score can give more than 25%. "No entrance exam" goes straight to the fee |
| "IB" | Asks for the IB points (the slabs use points, not %) |
| "60k rank, CSE" | Asks for the board marks too (marks can give a scholarship when the rank does not) |
| "MBA fee" | Asks only for the degree percentage (PG has no board or entrance slabs) |
| "Just the standard fee" / "skip" | Calculates with what it has |

- Each question is asked at most once, and details the student gave before (in the chat or in My details) are not asked again.
- Campus: SR University has one campus (Warangal), so it is never asked. In this brief "branch" was read as the B.Tech branch.
- The answer gives the scholarship and the score that earned it (only the best one applies). It also gives first-year tuition, per semester, semester-1 payable and the yearly increase, then one line on the 19 special category concessions and the link to the official calculator https://sru.edu.in/fee-scholarship/.
- Fee portal check: the Fee & Scholarship page on sru.edu.in shows the same 2027-28 tuition as the fee card for every programme. It also shows two offers that are not on the fee card (see section 8), and SRU Buddy does not apply them.

## 3. Follow-up suggestions (item 2)

Why they were unrelated:
- The old chips came from loose word matching: "timing" in "library timings" gave hostel chips, and "credit" inside "accredited" gave attendance chips.
- Almost every answer ends with an offer to calculate a fee, so the fallback produced fee chips everywhere.

The new chips:
- The topic comes from the tool that answered (fee, faculty, eligibility, concessions...), else from whole words in the question. Never from the answer.
- About 18 topics, each with chips that are natural next questions. Example after a personal fee: special category concessions, add hostel, eligibility for the same course, how to apply.
- Chips name the student's course when it is known ("Eligibility for B.Tech CSE").
- A chip that repeats the question is dropped.

The older chat endpoint (only used if the agent is down) keeps its old chips.

## 4. Faculty (item 3)

- Data: `backend/app/sru_agent/faculty_directory.json`, built from all 340 official profile pages on 17 Nov 2026. It covers name, Dean / Head role, designation, school, department, highest qualification, years of experience, research areas, interests, subjects, education and the profile link. No e-mail addresses or phone numbers are kept.
- Search (`faculty.py`, no AI call): by name (spelling-tolerant), by Dean / Head of a school or department, by department, and by research topic or subject ("who teaches VLSI in ECE", "faculty working on IoT"). Department questions give counts (faculty listed, with Ph.D., professors), the leaders and senior faculty.
- Faculty questions are looked up before the AI is called, so they need one AI call. The answer comes with a card showing the people and links to their official profiles.
- To refresh: `pip install beautifulsoup4`, then `python scripts/fetch_faculty_directory.py data/faculty_raw/new.json`, then `python scripts/build_faculty_directory.py data/faculty_raw/new.json`.

## 5. Strengths and formatting (items 4 and 5)

- New handbook page `12_strengths_faculty_and_visits_nov2026.md`, with the source of every line. The prompt has a short "WHY SRU" block: pick the 2-3 points that fit the question, word them freshly, always with the fact behind the claim.
- "Top university in Telangana and Andhra Pradesh": SRU Buddy may say "one of the top-ranked private universities of Telangana and Andhra Pradesh" only together with a rank:
  - 7th among private universities in India (THE 2027);
  - 19th among private universities in India (QS Asia 2027);
  - NIRF 91 in Engineering;
  - first private university in Telangana and AP with ICAR accreditation.

  No official page states "Top University in Telangana and AP" as such (see section 8).
- Placements now follow sru.edu.in/placements: average 6.5 LPA (the older handbook said 6), highest 51 LPA, 150+ recruiters, 1,300+ offers. No placement percentage is quoted because the page gives two different figures.
- Formatting rules as in the summary table. The fixed word counts per "style" were removed; the six styles now set only the tone.
- The prompt went from 9,669 to 7,465 characters while gaining these rules (it is sent with every AI call).

## 6. Widget (item 6)

Add it to any page, just before `</body>`:

```html
<script src="https://university-ai-companion.vercel.app/widget.js" defer></script>
```

- Options: `data-position="left"`, `data-color="#1d4ed8"`, `data-label="Ask SRU Buddy"`, `data-greeting="..."` (empty turns it off) and `data-open="true"`. From the page's JavaScript: `SRUBuddy.open()`, `SRUBuddy.close()`, `SRUBuddy.toggle()`.
- Try it at `https://university-ai-companion.vercel.app/widget-demo.html` after deploying.
- How it works: a floating SRU bubble (with a greeting shown once per visit) opens a 400 × 680 px chat window, full screen on phones. Inside is the same app with `?mode=widget`. Header buttons: calculator, new chat, open full screen, close.
- Same backend, knowledge, fee engine, faculty search and cards as the website, so every improvement reaches both. Each message is stored with `channel: web` or `channel: widget`, so the admin console can tell them apart.
- Nothing is loaded until the student hovers over, focuses or taps the bubble, so the host page stays fast. Esc closes it, and keyboard and screen-reader labels are included.
- The website itself is unchanged.

## 7. Campus visits (item 7)

- SRU Buddy never books, schedules, approves or confirms a visit, a date or a time, and quotes no visiting hours (sru.edu.in/visit-us lists none).
- "I want to visit" (with or without a date) gets an instant reply with the official contacts from the Visit Us page:
  - 0870-2818333 / 0870-2818311;
  - +91 70750 10336 (call or WhatsApp);
  - info@sru.edu.in;
  - the campus address.

  It also gets a contact card (Google Maps, Visit Us page).
- If the student wants, SRU Buddy passes their name and number on (`request_campus_visit_callback`). The lead is saved as type `campus_visit` with the note "NOT booked or confirmed: please call the student to arrange it" and any day they mentioned. The reply says clearly that it is not a booking.
- Removed: the date confirmation ("Do you mean 25 Nov?"), the visit booking form card and the `book_campus_visit` tool. Older chats that show the old form now show the contact card instead.
- Detailed visit questions ("can my parents come?") are answered by the AI under the same rules.

## 8. Latency (item 8)

**Measured on the live site on 17 Nov 2026** (from a browser, warm server):

| Message | First word | Complete |
|---|---|---|
| "hi" (no AI call at all) | 3.7 s | 5.2 s |
| A question answered from the saved-answer cache (no AI call) | 3.7 s | 5.4 s |
| "Tell me about placements" (1 AI call) | 4.9 s | 6.5 s |
| "What is the hostel fee?" (2 AI calls) | 7.8 s | 9.5 s |

**Causes:**
- About 29 separate trips to the hosted PostgreSQL and Redis, one after another, before and after every answer (rate limit, conversation lookup, profile, history, state, then saving).
- The chat was saved before the cards were sent: about 1.5 s.
- Some questions made two AI calls.
- Retry waits of 1.5, 4 and 8 seconds on a busy key.

**Fixes:**
- The server keeps each student's profile, chat context and state in its own memory, and writes Redis and the database in the background. Writes are in order and merged; they finish on shutdown, and the chat never waits for them. The three reads at the start of a message run together. A new chat gets its id without a database trip, and its first message does not look up an empty history.
- The answer and its cards are sent first; the chat is saved straight after.
- Gemini's answer is streamed to the browser while it is written, instead of after it is complete. Callback, visit and cancellation replies are still checked for honesty before they are shown.
- Least thinking (`MINIMAL`, or `LOW` where a model has no MINIMAL). This is automatically dropped if a model refuses it.
- Fee questions with all details, and faculty questions, are calculated / looked up before the AI call, so they need one AI call. Fee follow-up questions are asked without any AI call.
- Retry waits shortened to 1 and 2.5 s; prompt 23% shorter.

**Measured here** (same tests run on v2.9.0 and v3.0.0, with 100 ms added to every database / Redis trip to imitate the hosted services and a stand-in AI that takes 1 s):

| | v2.9.0 | v3.0.0 |
|---|---|---|
| "hi", new chat: first word | 2.92 s | 0.88 s |
| Question with a 1-second AI answer: first word | 2.04 s | 1.02 s |
| Same question: complete (cards shown) | 3.30 s | 1.02 s |

With the real Gemini, streaming should bring the first words 1-2 seconds earlier again. This could not be measured here (no Google access from the test machine).

**Settings** (all optional, defaults shown): `AGENT_THINKING_LEVEL=MINIMAL`, `AGENT_STREAM=true`, `AGENT_LOCAL_CACHE=true`, `AGENT_BACKGROUND_WRITES=true`, `AGENT_RETRY_DELAYS=1,2.5`, `AGENT_CALL_TIMEOUT=25`.
- The in-memory copy is right because Render runs one server process. If you ever run several processes or instances, set `AGENT_LOCAL_CACHE=false`.
- **If Render has `AGENT_RETRY_DELAYS=1.5,4,8` set** (it was in the old `.env.example`), change or delete it.

## 9. For the Admissions Office to confirm

1. Website-only offers on sru.edu.in/fee-scholarship: "extra 10% scholarship on all PG programmes", and "first arrival admission benefit, Rs 25,000 admission fee waived before 12 April 2026" (that date has passed). Neither is on the 2027-28 fee card, so SRU Buddy does not apply them.
2. Placement rate: the placements page says both 92% and 95%. Average package: 6.5 LPA on the page, 6 LPA in the handbook.
3. WhatsApp: the Visit Us page gives +91 70750 10336, while the chat's general WhatsApp setting (`ADMISSIONS_WHATSAPP`) is +91 83310 03030. Which should students use for general questions?
4. "Top University in Telangana and AP": if the university wants this exact phrase, give the official source. Until then SRU Buddy uses it only with a rank.
5. Visiting hours: not published; SRU Buddy tells students to confirm with the admissions team.
6. From earlier rounds, still open: 2027-28 minimum marks, documents list, early-bird offer.

## 10. Tests

| Check | Result |
|---|---|
| Backend tests with PostgreSQL | 511 passed, 1 skipped (new: `test_round3_speed.py`, `test_round3_features.py`) |
| Backend tests without a database | 503 passed; the same 2 database-only tests fail as in v2.9.0 |
| Frontend build | Passes |
| Fee calculator vs fee card | 3,477 checks passed |
| Browser journey | Fee details asked, then fee card; faculty card for "head of CSE"; visit guidance + contact card + "not a booking" request card; library question gets campus chips; widget opens, answers and closes on a host page; phone full screen with no overflow; no console errors |

Tests that described the old behaviour (visit booking, date confirmation, fees calculated without asking) were rewritten for the new rules, not deleted.

**Not tested here:**
- The real Gemini with streaming and the thinking setting.
- The widget on the real sru.edu.in page and in Safari.
- Real phones.

The thinking setting falls back automatically if a model refuses it, and `AGENT_STREAM=false` turns streaming off without a code change.

## 11. After merging

1. Deploy as usual (Render, Vercel). No database migration.
2. Check Render's environment for `AGENT_RETRY_DELAYS` (section 8).
3. On the live site, try:
   - "CSE fee", then "State board 85%, no entrance exam";
   - "Who is the head of CSE?";
   - "I want to visit the campus";
   - the widget demo page.
4. To put the widget on the admission page: send the one-line script (section 6) to whoever edits sru.edu.in.
