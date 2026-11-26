# API Specification

## Auth
POST /api/v1/auth/login
POST /api/v1/auth/register
POST /api/v1/auth/refresh

## Chat
POST /api/v1/chat
POST /api/v1/chat/stream
GET /api/v1/conversations
GET /api/v1/conversations/{conversation_id}
DELETE /api/v1/conversations/{conversation_id}

## Conversation Recovery (v4.0.0)
GET /api/v1/agent/recovery-context?session_id=...
POST /api/v1/agent/reset-session

Returns structured previous conversation context for returning students (Section 4 personalized welcome message, scholarship status, calculated fee waiver, program, board, stage, and relative active time).
The reset endpoint starts a fresh conversation while preserving verified identity (name, phone) and historical database records.

v4.8.0 additions to `GET /recovery-context`:

| Field | Meaning |
|---|---|
| `inactive_minutes` | Minutes since the last message of that conversation (`null` when unknown) |
| `resume_after_minutes` | The threshold (`RECOVERY_RESUME_AFTER_MINUTES`, 30) |
| `offer_choice` | `true`: ask "continue or start new". `false`: the conversation simply continues |
| `last_user_message` | The student's last question (up to 120 characters), shown in the choice |

- The conversation offered is the one with the latest message (not the latest created). `last_active_at` is that
  message's time.
- `POST /reset-session` no longer clears the previous conversation's state. It files the academic details with the
  previous conversation, removes the programme from the active profile, keeps name and mobile, and returns
  `active_conversation_id` (the previous one) and `new_conversation_id`.


## Feedback
POST /api/v1/feedback

## Deterministic finance tools
POST /api/v1/finance/estimate
GET /api/v1/admin/finance-rules
PUT /api/v1/admin/finance-rules
GET /api/v1/admin/agent-runs
GET /api/v1/admin/calculations

Finance estimates are calculated only from versioned official rules in the finance
catalog. If a matching fee or scholarship rule is unavailable, the endpoint returns
`status: "insufficient_data"` rather than inventing an amount.
The admin endpoints require `X-Admin-Key` and publish the validated catalog atomically.

## Memory controls
GET /api/v1/memory?session_id=...
POST /api/v1/memory
DELETE /api/v1/memory/{key}
GET /api/v1/memory/conversations/{conversation_id}/summary?session_id=...
GET /api/v1/memory/calculations?session_id=...
DELETE /api/v1/memory/calculations?session_id=...

Memory writes require explicit consent and are limited to non-sensitive preferences.
Raw messages remain the source of truth; summaries are bounded context and are
deleted with their conversation.

The chat orchestrator routes explicit calculation requests containing fee or
scholarship intent to this deterministic tool. Ordinary informational questions
continue through the existing intent/RAG/LLM path. Responses expose an optional
`agent` field such as `{ "agent": "finance", "status": "executed" }`.

Agent execution is bounded by an allowlisted tool registry and a maximum of
three steps. The model cannot invoke arbitrary endpoints or services.
Each agent execution is also persisted in `agent_runs` with its route, selected
tool, policy reason, status, step count, conversation, and response message.
Administrators can inspect recent records through `/api/v1/admin/agent-runs`.
Finance calculations additionally persist their explicit inputs, result status,
result payload, source references, and originating message in
`calculation_scenarios`.
When required finance inputs are missing, the agent stores a pending
`pending_agent_tasks` record and resumes it when the user supplies the missing
details in the same conversation.

Pending clarification tasks can be listed with
`GET /api/v1/memory/pending-tasks?session_id=...` and cancelled with
`DELETE /api/v1/memory/pending-tasks/{conversation_id}?session_id=...`.
Both endpoints enforce browser-session ownership.
Administrators can inspect recent scenarios through `/api/v1/admin/calculations`.
Users can inspect only their own session's calculations through
`/api/v1/memory/calculations`.
They can delete that calculation history without deleting the associated chat
conversation through `DELETE /api/v1/memory/calculations`.

## Admin
POST /api/v1/admin/documents
GET /api/v1/admin/documents
POST /api/v1/admin/documents/{id}/reindex
DELETE /api/v1/admin/documents/{id}
GET /api/v1/admin/stats
GET /api/v1/admin/feedback
GET /api/v1/admin/conversations
GET /api/v1/admin/conversations/export
GET /api/v1/admin/conversations/{conversation_id}
DELETE /api/v1/admin/conversations/{conversation_id}
POST /api/v1/admin/exemplars/promote



## Chat request example

```json
{
  "session_id": "browser-session-uuid",
  "conversation_id": "uuid-or-null",
  "message": "When is exam registration?"
}
```

## Chat response example

```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "answer": "According to ...",
  "sources": [
    {
      "document_id": "uuid",
      "title": "Academic Calendar",
      "page": 4
    }
  ],
  "suggestions": [
    "📋 How to Apply",
    "💰 Fee Structure"
  ],
  "cards": [
    {
      "type": "video_recommendations",
      "title": "Official SR University Video Tours",
      "channel_name": "SR University Official",
      "channel_url": "https://www.youtube.com/@SRUniversity/videos",
      "videos": [
        {
          "id": "9kYIkkadZkU",
          "title": "SR University Campus Tour",
          "url": "https://www.youtube.com/watch?v=9kYIkkadZkU",
          "thumbnail_url": "https://img.youtube.com/vi/9kYIkkadZkU/hqdefault.jpg",
          "category": "Campus Tour",
          "duration": "3:45"
        }
      ]
    }
  ],
  "flow": null,
  "model": "gemini-3.5-flash-lite"
}
```

## Chat SSE Stream format
`POST /api/v1/chat/stream` returns `text/event-stream` chunks:
- `data: {"type": "start", "conversation_id": "uuid"}`
- `data: {"type": "token", "delta": "word "}`
- `data: {"type": "done", "conversation_id": "uuid", "message_id": "uuid", "answer": "...", "sources": [...], "suggestions": [...], "cards": [...], "flow": null, "model": "..."}`

## Feedback request example

```json
{
  "session_id": "browser-session-uuid",
  "conversation_id": "uuid",
  "message_id": "uuid",
  "rating": 1,
  "comment": "Accurate and clear answer."
}
```

## Feedback response example

```json
{
  "id": "uuid",
  "status": "received"
}
```

## Public Access Model
For public anonymous access, endpoints use `session_id` (a browser-generated UUID stored in localStorage) to track conversations and feedback without requiring student login or signup. Admin endpoints (`/api/v1/admin/*`) require the `X-Admin-Key` header.
GET `/api/v1/admin/feedback` returns feedback items with `question` and `answer` context. Positive feedback (rating=1) automatically indexes the Q&A into ChromaDB collection `verified_exemplars` for dynamic few-shot self-improvement.

## Model Evaluation & Benchmark Endpoints (Admin Only)
- `POST /api/v1/admin/evaluations/run`: Executes benchmark suite from `evaluation/evaluation_dataset.jsonl` against RAG and stores results in `evaluation_records`.
- `GET /api/v1/admin/evaluations`: Paginated list of benchmark and response evaluation records with groundedness scores, latencies, and pass/fail indicators.

Use consistent error schemas and HTTP status codes.

## Admissions agent endpoints (v2.7.0)

```http
POST /api/v1/agent/stream        # SSE: start, tool, token, done, error
POST /api/v1/agent/calculate     # fee + scholarship for one student (same code the agent uses)
GET  /api/v1/agent/programs      # programs with tuition and minimum marks
GET  /api/v1/agent/fee-config    # everything the Fee & Scholarship Calculator draws from
```

`POST /api/v1/agent/stream` body: `session_id`, `message`, `conversation_id?`, `channel?`
(`web` | `widget`), `source?` (v4.17.0: `typed` (default) when the student typed the message, `button` when it is
the text of a chip, card option or tile the bot offered; any other value is rejected with 422; see
`docs/43-model-first-understanding-nov-2026.md`), and, only when the student submits the academic details form (card type
`academic_details_form`, v4.6.0), `form`:

| Field | Values |
|---|---|
| `mode` | `eligibility` \| `scholarship` |
| `program` | programme key from `fee_policy_2027_28.json` (e.g. `btech_cse`) |
| `board_key` | `ts_state_board` \| `ap_state_board` \| `cbse` \| `icse` \| `other_state_board` \| `ib` |
| `academic_stage` | `1st_year` \| `2nd_year` \| `completed` |
| `raw_marks`, `max_marks` | numbers (IB: points out of 45) |
| `stream` | `MPC` \| `BiPC` \| `MEC` (when the form asked for it: `show_stream`) |
| `entrance_type`, `entrance_value` | `none` \| `tg_eapcet` \| `ap_eapcet` \| `jee_main`, with the rank / percentile (optional; `show_entrance`) |

The agent validates the values again. A form with problems is returned with what was entered and nothing is
saved; a valid form is stored as this conversation's academic details and evaluated (eligibility or scholarship).
`message` is the readable summary shown in the chat.

`POST /api/v1/agent/calculate` body: `program` (required), `percent`, `board`
(`state_board` | `cbse`), `eapcet_rank`, `jee_percentile`, `ib_score`, `hostel`
(`none` | `non_ac_4` | `non_ac_3` | `ac_4` | `ac_3`), `specialization`, `transport`, `concessions`
(list of concession keys from the fee policy, at most 5; v4.16.0).

Response (v4.16.0, the ONE fee engine `app/sru_agent/fees.py`, policy `fee_policy_2027_28.json`): besides
`scholarship_percent`, `tuition_first_year`, `tuition_first_year_after_scholarship`, `per_semester_after_scholarship`
(tuition only), `saving_first_year`, `first_year_total_payable`, `full_course_total`, `year_by_year[]`
(`tuition`, `after_scholarship`, `per_semester`, `total_payable`) and `next_scholarship_slab`, it returns:

| Field | Meaning |
|---|---|
| `semester_1`, `semester_2` | `{items: [{key, item, amount, kind}], total}` for Year 1; `kind` is `tuition`, `charge`, `optional` or `concession` |
| `sem1_total_payable`, `sem2_total_payable` | the two semester payables (Year 1) |
| `schedule[]` | every year: `{year, annual_tuition, semesters: [...], total}` |
| `application_fee` | shown separately; never part of a semester |
| `one_time_enrollment_fee`, `exam_fee_first_year`, `other_fee_per_year`, `specialization_fee_per_year` | the circular's charges |
| `concessions_applied[]` | `{category, per_year}` |
| `flags[]` | points the Admissions Office must verify (marks below the minimum, PG minimum, JEE 94.5-95 gap, IB overlap, combined concessions) |
| `admission_eligibility` | `{status, eligible, explanation}` when a percentage was given |

Removed in v4.16.0: `other_yearly_fees`, `other_fees_per_semester`, `one_time_application_fee`, `one_time_total`,
`per_sem_breakdown`, `hostel.per_semester` (the old "annual payable / 2" figures). `total_per_semester` now means
the Year 1, Semester 2 payable.

`GET /api/v1/agent/fee-config` (v4.16.0): `charges`, `schedule` (the configurable assumptions), `hostel_per_year`,
`hostel_status`, `special_concessions` (claimable ones only), `terms` and `programs[]`; each programme's `slabs[]`
carries the engine's own figures per scholarship slab (`annual_tuition`, `saving_per_year`, `tuition_per_semester`,
`semesters[]`, `first_year_total`, `course_total`, `years[]`). The website calculator displays these and never
computes a fee. Removed: `one_time`, `yearly_other`, `transport_per_year`, `hostel_deposits`, `payable_per_semester`.

`POST /api/v1/leads` is limited to 30 requests per minute per address (HTTP 429 above that).
Admin routes return HTTP 503 while `ADMIN_API_KEY` is the placeholder and `APP_DEBUG=false`.
See `docs/24-agent-audit-nov-2026.md`.

## Student profile endpoints (v2.8.0)

```http
GET    /api/v1/agent/profile?session_id=...     # what the agent knows: name, phone, course, marks
PUT    /api/v1/agent/profile                    # {session_id, name?, phone?, program_interest?, fresh_start?}
DELETE /api/v1/agent/profile?session_id=...     # forget this student
```

`PUT` validates the mobile number (422 when it is not a 10-digit Indian mobile number) and also
corrects it on a callback / visit request already saved from that browser. The `done` event of
`POST /api/v1/agent/stream` now carries `profile` (the same object) and the saved message carries
`cards` and `suggestions`, so a reopened chat looks the same. `POST /api/v1/chat/stream` returns
429 above 20 messages a minute per session. See `docs/25-audit-round-2-nov-2026.md`.

`fresh_start` (v4.10.0, optional boolean): `true` when the browser copies its saved name and number into a session
started with "Start a new chat". The details are kept for the contact form and callbacks, but the conversation
does not address the student by name and the model is not given it (profile key `address_by_name: false`).

### Cards added in v4.10.0 (in the `done` event's `cards`)

| `type` | `data` |
|---|---|
| `get_special_concessions` | `all_categories` [{`category`, `per_year`}], `academic_year`, `note`, `program` (current programme or null). The browser shows a selectable table; "Apply to my fee" sends `Apply the "<category>" concession to my fee` |
| `concession_fee` | `program`, `program_key`, `academic_year`, `concession`, `concession_amount`, `tuition`, `tuition_after_concession`, `per_semester_after_concession`, `proof_note`, and with a merit scholarship `merit_percent`, `tuition_after_merit`, `combine_note` |
| `fee_plan` | `program`, `program_key`, `academic_year`, `rows` [{`item`, `amount`, `kind`: `fee` \| `discount`, `note`?}], `first_year_total`, `per_semester`, `application_fee`, `not_included`, `concession`? {`label`, `amount`, `total_if_approved`, `note`}, `share_text` |

The agent no longer caches answers (`AGENT_ANSWER_CACHE_SECONDS` is ignored). See
`docs/33-fresh-answers-and-fee-plans-nov-2026.md`.

### Fee evaluation agent cards (v4.11.0, `docs/34-fee-evaluation-agent-nov-2026.md`)

| `type` | `data` |
|---|---|
| `fee_summary` | `program`, `program_key`, `course`, `academic_year`, `category`, `rows` [{`item`, `amount`, `kind`: `fee` \| `discount` \| `pending`, `status`?, `note`?}], `original_tuition`, `scholarship` {`status`: `applied` \| `estimated` \| `not_eligible` \| `not_evaluated` \| `not_requested`, `label`, `amount`}, `special_consideration` {`status`: `pending` \| `none` \| `not_explored`, `category`, `amount`, `label`}, `total_approved_concessions`, `payable_confirmed`, `payable_after_approval` (null when nothing is pending), `pending` [text], `application_fee`, `combine_note`, `share_text` |

`concession_fee` and `fee_plan` (v4.10.0) are no longer produced; old chats still render them. The evaluation's
selections are kept in the conversation state under `fee_eval` (not exposed by the API).

## Security hardening (v4.7.0, `security/API_SECURITY.md`)

| Change | Contract |
|---|---|
| Session IDs | Every endpoint that takes `session_id` (query or body) requires 16-64 characters from `A-Z a-z 0-9 _ -` (the app sends a UUID). Anything else: HTTP 422 |
| AI-backed turns (`/agent/stream`, `/chat`, `/chat/stream`) | Limits: 20 per minute per session, `AI_IP_RATE_LIMIT_PER_MIN` (40) per minute and `AI_IP_DAILY_LIMIT` (600) per day per network, `AI_DAILY_TURN_BUDGET` (20,000) per day for the server. Over a limit: `/agent/stream` sends an SSE `error` event, `/chat*` return HTTP 429 |
| Request size | Bodies over `MAX_REQUEST_BYTES` (256 KB; admin document upload: `MAX_UPLOAD_BYTES`, 50 MB) get HTTP 413 before they are read |
| `GET /api/v1/conversations/{id}` | The `admin_key` query parameter is removed. Staff send `X-Admin-Key`; a wrong key gets 403 / 429 like the admin routes |
| `POST /api/v1/feedback` | HTTP 404 unless the message belongs to a conversation of the same `session_id` |
| Admin routes | HTTP 503 while `ADMIN_API_KEY` is the placeholder on a production server (`APP_ENV=production`, on Render, or `APP_DEBUG=false`) |
| `/docs`, `/openapi.json` | Only on a development machine (`APP_DEBUG=true`, not production) |
| Errors | Production error messages never name internal services, hosts or ports |

## v4.12.0 endpoints (`docs/35-agentic-features-and-admin-switches-nov-2026.md`)

```http
GET  /ping                                              # keep-awake: {"status": "ok"}, touches nothing (also HEAD)
GET  /api/v1/agent/connect/{request_id}?session_id=…    # "talk to a counsellor" status, the student's own request only
GET  /api/v1/admin/settings                             # chat settings (admin key)
PUT  /api/v1/admin/settings                             # change some settings (admin key; audited)
GET  /api/v1/admin/live-requests                        # students waiting for a counsellor now
POST /api/v1/admin/live-requests/{request_id}/accept?counsellor=Name   # first counsellor wins; 409 if too late
GET  /api/v1/admin/copilot/priorities?limit=20          # who to call first: ranked open leads with reasons
GET  /api/v1/admin/copilot/draft/{lead_id}              # a draft follow-up message (nothing is sent)
```

| Shape | Fields |
|---|---|
| Connect status | `request_id`, `status` (`waiting` \| `accepted` \| `busy`), `seconds_left`, `wait_seconds`, `phone_last4`, `counsellor` |
| Settings (`PUT` body: any subset) | `concession_picker` (`grouped` \| `table`), `connect_enabled` (bool), `connect_wait_seconds` (10–120), `office_hours_start` / `office_hours_end` ("HH:MM", India time), `office_days` (0 = Monday … 6 = Sunday). 422 on an invalid value |

New cards in `done.cards`:
- `agent_plan`: `{title, steps: [{title, status: done | now | todo | skipped, detail}]}`
- `counsellor_connect`: the connect status above
- `get_special_concessions`: now also carries `mode` (`grouped` | `table`) and `allow_none`, and with grouped mode
  `groups` [{`key`, `title`, `hint`, `private`, `items` [{`category`, `per_year`}]}]

Callback / visit leads carry `metadata.case`: `program`, `marks`, `scholarship`, `concession`, `hostel`, `fee`,
`asked` (numbers masked) and `signals`.



### v4.15.0 notes (no breaking change)

* `GET /api/v1/agent/connect/{request_id}` also returns `first_name` (the name shown on the student's callback card).
* `GET /api/v1/agent/recovery-context`: `welcome_message` uses the first name ("Welcome back, Mahesh!") and
  `score_text` has no trailing ".0" ("764 / 1000 (76.4%)").
* `POST /api/v1/leads`: a repeat callback / visit request from the same mobile number within 7 days (lead still
  `new`) returns the existing lead, updated, instead of a new one.
* `PUT /api/v1/agent/profile` with `fresh_start` keeps the student's name usable in the new chat.


### v4.15.1

* `POST /api/v1/admin/media` (admin): upload a JPEG / PNG / WebP (≤ 450 KB) for an ad or event card; returns
  `{id, url, type, size}`. `GET /api/v1/agent/media/{id}` (public) serves it. See docs/41.
* `chat_ads[].image_url` and `event_highlights[].image_url` accept `/api/v1/agent/media/<id>` as well as https:// links.
* Admin conversations list / detail: new optional `student` object (name, phone, program, marks, scholarship_percent,
  request, lead_status, is_parent).


### v4.17.1: Reply and Edit (`docs/45-reply-and-edit-nov-2026.md`)

`POST /api/v1/agent/stream` body, new optional fields (each a message UUID):

| Field | Meaning | Refused (SSE `error`, `code: "message_action"`, nothing changed) when |
|---|---|---|
| `reply_to` | The student replies to this saved message (a fee card's message included). The model is given that message and, for a fee card, that card's own estimate, and is told when a newer estimate exists. | the message is not in this student's conversation |
| `edit_of` | This message replaces the student's latest **typed** message. The state from before that message is restored; it and every later message are archived (`metadata.superseded`, never deleted); the new text is answered. | it is not the latest typed message, it was a button choice, the state from before it is no longer kept, or that turn or a later one started an admissions request (callback / visit) |

The `done` event now also carries `message_id` (the saved answer), `user_message_id` (the saved student message)
and `user_metadata` (`source`, and when set `edited`, `reply_to`, `action_done`). Both messages are saved with
these ids, so Reply / Edit can refer to them.

`GET /api/v1/conversations/{id}` messages: new fields `edited` (bool), `reply_to` (message id or null), `source`
(`typed` / `button` / null for older messages) and `action_done` (bool: the message started an admissions request
and cannot be edited). Messages replaced by an edit are not returned. No database migration: these live in the
existing `messages.metadata` JSON column.
