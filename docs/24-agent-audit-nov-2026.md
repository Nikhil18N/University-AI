# 24. Agent audit and fixes (17 Nov 2026, v2.7.0)

Branch: `fix/agent-audit-nov16`. Prompt version: `2026-11-17.1` (`backend/app/sru_agent/prompt.py`).

This document records what the audit found, what was changed, how to deploy it, and what the
university still has to confirm. It is written so a student developer can follow it without
reading the whole diff.

## 1. What the audit found

| # | Finding | Where | Effect on students |
|---|---|---|---|
| 1 | Four separate copies of the fee data that disagreed with each other and with the official circular | `fees_2027_28.json`, `ScholarshipCalculatorModal.tsx`, `card_service.py`, `prompt.py` | Chat, calculator and cards could show different fees for the same question |
| 2 | The fee file itself differed from the circular (B.Des, B.Sc Agri, MCA, M.Tech, MBA increase, PG slabs 15/25/35, EAPCET 1-8000 = 40%, an extra 20,001-60,000 slab, a ₹25,000 "admission fee") | `fees_2027_28.json` | Wrong amounts and wrong scholarship % |
| 3 | Yearly increase was discounted by the scholarship. The circular says "Yearly Fee Increase (Irrespective of Schol.)" | `fees.py` | Year 2-4 fees understated |
| 4 | The agent said "I have cancelled the callback" with no tool behind it; there was no way to cancel | `agent.py`, `tools.py` | A false statement to a student or parent |
| 5 | A callback was only saved if the model chose to call the tool; when the name and number came in a later message it was often just "noted" | `agent.py` | Lost leads, students waiting for a call that never comes |
| 6 | The date reader only understood a bare date. "Visit on 20 Nov, I am Ravi, 98..." or a past date gave a blank or wrong reply | `tools.py` | Blank replies |
| 7 | "Campus visit" canned question replaced real answers to longer visit questions | `agent.py` | Unhelpful reply |
| 8 | A generic "B.Tech CSE fee" card (₹2,42,500 etc.) was appended under personalised fee answers | `agent.py`, `card_service.py` | Two different totals on one screen |
| 9 | Fee cards carried hand-typed amounts: hostel ₹85,000-95,000, bus ₹22,000, admission fee ₹25,000 | `card_service.py` | Wrong amounts |
| 10 | The agent used only the first Gemini key, never retried, and sent a ~14,700 character prompt with every model call | `agent.py`, `prompt.py` | 20 students at once: 5 answered, 15 failed |
| 11 | The calculator did not notice "EAPCET 9000" unless EAPCET was selected, kept an old "Rank 9,000" label, and saved a lead on every keystroke for verified students | `ScholarshipCalculatorModal.tsx` | Wrong fee shown, duplicate leads |
| 12 | The calculator's first-year total left out the ₹20,000 yearly other and exam fees; hostel shown as ₹95,000 | `ScholarshipCalculatorModal.tsx` | Total lower than the chat's total |
| 13 | The placeholder admin key `change-me-in-production` was accepted, compared with `!=` | `deps.py` | Anyone reading the source could open the leads list |
| 14 | `/api/v1/leads` is public and had no limit | `lead.py` | A script could flood the leads table |
| 15 | Without Redis, chats kept in server memory were never removed | `memory.py` | Slow memory growth on a long-running server |
| 16 | Secrets were inside the shared zip (`backend/.env`, `.env.local`, `.env.vercel`, `.env.production.local`). They are not in git | project folder | Keys must be rotated (section 5) |

## 2. What changed

### One source of truth for fees
* `backend/app/sru_agent/fees_2027_28.json` was rebuilt line by line from the official circular
  (`backend/data/handbook/08_admissions_fees_scholarships_and_eligibility.md`): 26 programs, one
  UG slab matrix, PG slabs, hostel, deposits, 20 special concessions.
* `fees.py` now also provides `program_info`, `special_concessions`, `compare_programs` and
  `fee_config`. The yearly increase is flat, as the circular says.
* The calculator has **no amounts of its own**. It reads `GET /api/v1/agent/fee-config` and
  confirms every result with `POST /api/v1/agent/calculate`. A generated copy
  (`frontend/src/data/feeConfig.json`) is bundled so it opens instantly.
* The hostel, transport and admission cards in `card_service.py` are built from the fee file.
* The agent prompt contains no fee numbers.

**To change a fee:** edit `fees_2027_28.json`, then in `backend/` run
`python scripts/export_fee_config.py`, then `pytest` and (in `frontend/`) `npm test`. Tests fail
if any copy is out of date.

### Actions the agent takes itself
The agent no longer depends on the model deciding to call a tool for these:

| Student says | What happens | Model needed? |
|---|---|---|
| "ask someone to call me" then later "Ravi Kumar 9876543210" | The request is remembered as pending; when name + number are known the lead is saved and the reference is given | No |
| "call me on 12345" | The number is refused, nothing is saved | No |
| "don't call me" / "cancel my visit" | `cancel_contact_request` runs; the lead is marked `do_not_contact`. The reply says "cancelled" only if that really happened | No |
| "Book a visit on 20 Nov for 3 people. Ravi 98..." | Booked in one step | No |
| Visit on a past date / Sunday / beyond 90 days | A clear reason and a request for another date | No |

After every model answer two honesty checks run: the answer may not say a request was *saved* or
*cancelled* unless a tool returned that status in the same turn. If it does, the tool is run or the
sentence is replaced with the truth.

### New tools
`get_program_info`, `compare_programs`, `get_special_concessions`, `cancel_contact_request`,
`share_fee_estimate` (a WhatsApp link with the student's estimate, to send to parents).
`calculate_fee` now accepts `ib_score` and `transport` and remembers the marks it was given.

### Load
* Every key in `GEMINI_API_KEYS` is used in turn; a rate-limited key is rested and the next one
  is tried at once; busy errors are retried (1.5 s, 4 s, 8 s).
* At most `AGENT_MAX_CONCURRENCY` (6) model calls run together; the rest wait instead of failing.
* The prompt went from about 14,700 to about 6,400 characters.
* If the model cannot be reached at all, fee questions are still answered from the fee file.

### Security
* The placeholder admin key is refused when `APP_DEBUG=false`; keys are compared in constant time.
* `/api/v1/leads` allows 30 requests per minute per address.

### Website
* Calculator rewritten on top of the fee table (see above); "EAPCET 9000" is understood whatever
  is selected; leads are saved only when a button is pressed; four hostel options with the official
  prices; first-year total includes other and exam fees.
* "BETA" label restored in the header. Admin lead status list has "Do not contact".

## 3. New and changed API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/agent/fee-config` | New. Programs, exams, slabs (text and numeric bounds), hostel, one-time fees, concessions |
| POST | `/api/v1/agent/calculate` | Now also accepts `ib_score` (0-45) and `transport` (bool) |
| POST | `/api/v1/leads` | Unchanged body. Returns 429 above 30 requests a minute from one address |
| any | `/api/v1/admin/*` | Returns 503 while `ADMIN_API_KEY` is the placeholder and `APP_DEBUG=false` |

No database migration is needed. Lead status is a free text column; the new value is
`do_not_contact`, and `metadata` gains `cancelled_at`, `cancel_reason`, `consent: false`.

## 4. How to deploy

1. Merge `fix/agent-audit-nov16`.
2. **Render (backend) environment:**
   * `GEMINI_API_KEYS` = comma-separated keys from *separate* Google Cloud projects (see section 5).
   * `ADMIN_API_KEY` = a long random value (not the placeholder).
   * `APP_DEBUG=false`, `APP_ENV=production`.
   * `REDIS_URL` set, so pending requests and profiles survive a restart.
3. **Vercel (frontend):** redeploy. `VITE_API_BASE_URL` stays as it is.
4. Check: `GET /health`, then `GET /api/v1/agent/fee-config`, then in the chat:
   "cse fee with 85%" (25%, ₹2,55,000), "ask someone to call me" then a name and number,
   then "don't call me".

## 5. Still needed from the university / the team

* **Rotate the secrets** that were in the shared zip: Gemini key(s), the Neon/Postgres password,
  the Redis URL, the admin key, the Vercel token.
* **Gemini capacity.** Code can spread and retry, but it cannot create quota. For an admissions
  page, use a paid Gemini tier or several keys from separate projects. With one free key, a class
  of students using it together will still be slowed.
* **Please confirm with the Admissions Office** (the bot currently says these, but they are not in
  the fee circular):
  1. CSE and ECE: is 50-54.9% admissible? (the circular's base band starts at 55% for them)
  2. JEE Main 30% slab: the circular says 90-94.5; 94.5-94.99 is treated as 30%.
  3. IB slabs: the circular lists 30-37 and "35/45 and above" (overlap). Used: 34-37 = 30%, 38+ = 40%.
  4. AC hostel electricity deposit: ₹5,000 in one table, ₹10,000 in another.
  5. Admission fee: the circular has none (only ₹5,000 enrollment and ₹1,100 application). The old
     ₹25,000 was removed from the admission card.
  6. Early-bird 50% application offer (₹550): shown in an ad card and the legacy prompt.
  7. Hostel in-times (8:30 PM first years, 9:00/9:30 PM seniors).
  8. "6 LPA average" placement figure and the three top offers with batch years.
  9. Campus visit hours "Monday to Saturday, 9:30 AM to 4:30 PM".
* **Documents required at admission:** there is no such list in the knowledge base, so the agent
  correctly says it cannot confirm it. Add the official list to `backend/data/handbook/` and
  re-ingest.
* Delete the two test leads created during live testing: "Test QA" 9000000001 (ref `de55b9ab`) and
  "Test QA" 9000000002 (ref `4a262474`).

## 6. Tests

| Command | Result on 17 Nov 2026 |
|---|---|
| `cd backend && pytest` (PostgreSQL running) | 431 passed, 0 failed |
| `cd backend && pytest` (no database) | 423 passed, 6 skipped, 2 failed. Those 8 need PostgreSQL; before the changes the same run gave 360 passed, 6 skipped, 2 failed |
| `cd frontend && npm test` | 3,438 checks: the calculator's arithmetic equals the backend's for 338 inputs |
| `cd frontend && npm run build` | passes |

New test files: `backend/tests/test_agent_actions.py` (34 tests: cancel, callback, visit, honesty
checks, key rotation, retry, 20 students at once), `backend/tests/test_fee_single_source.py`
(fee file against the circular, calculator API, cards, admin key, lead cancel).

Also checked by hand: the built website's calculator in a real browser against the API
(typing "EAPCET 9000" with State Board selected gives 25%, one API call, no lead saved), and the
real lead save / cancel path against a local PostgreSQL.

Not tested here: a live Gemini call and the production database (the audit environment has no
network access to them, and the keys in the zip were deliberately not used). Run the section 4
checks after deploying.
