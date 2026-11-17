# 26. Production readiness (17 Nov 2026, v2.9.0)

Base: v2.8.0 (commit `5314637`). The Gemini free API is unchanged, as asked: no model, key or
provider changes in this round.

This round is about what a student, a parent and the university's IT team need before SRU Buddy
goes on the admission page: a clean interface on every screen size, no unconfirmed offers, the
staff console out of public view, safer server settings, and a server that answers in the morning.

## 1. What was found

Found by a full screen tour (phone 390 px, tablet 820 px, desktop 1440 px, light and dark), the
v2.8.0 test suite, and a review of the server's settings.

| # | Finding | Effect on a student |
|---|---|---|
| 1 | The "Admin console" button was shown to every visitor | Students could reach the staff login screen |
| 2 | The "Early Bird 50% off" card and the "Apply with 50% Off" chip were shown, but the offer is not on the 2027-28 fee card | A promise the university has not confirmed |
| 3 | "I want to visit campus on 25 Nov" was treated as a question about visits, not a booking | The student had to type the date again |
| 4 | Desktop header: the Share button sat underneath the centre menu; button labels overlapped between 769 and 1240 px | Buttons hard to find or click |
| 5 | The calculator could not be opened on a phone | Main fee tool missing on most students' devices |
| 6 | The "AI can make mistakes" note was repeated under every single answer | Long, cluttered chats |
| 7 | The "thinking" animation listed fixed made-up steps ("Searching 64+ sources…") | Not true; looked fake when the server was slow |
| 8 | The first answer of the day can take 30-60 seconds (the free Render server sleeps) and nothing explained it | Students leave thinking it is broken |
| 9 | The details form was compulsory-looking ("Verify to continue"), and closing it dropped the student's question | Lost questions, lower trust |
| 10 | Error messages mentioned Docker and gave no phone number | Not useful to a student |
| 11 | The server's error handler copied back any website's address as "allowed", with credentials | Weak browser security |
| 12 | No security headers on the server or the site | Fails a basic security scan |
| 13 | Chats were titled "hi" or "hello" in the history and in the staff console | Hard for staff to find real questions |
| 14 | Text as small as 8.7 px and tap targets as small as 21×17 px | Hard to read and tap on a phone |
| 15 | The browser zoom was blocked on phones; page titles still said "2026" | Accessibility; wrong year in search results |

## 2. What was changed

### Student-facing
- **Header**: one "Share" menu (share link, PDF/print, Markdown) instead of two overlapping buttons;
  icons instead of emoji; labels hide on mid-size screens instead of overlapping.
- **Phone menu**: the calculator is now the first item; clearer labels ("Share chat link",
  "Save as PDF / Print", "Reply sound: on/off").
- **Input box**: new quick actions (How to apply, B.Tech fees, Hostel, Placements, Book a visit);
  voice typing where the browser supports it (Indian English); a real send button that is disabled
  while the box is empty; one disclaimer under the box with the Admissions Office number
  0870-2818333; 2,000-character limit.
- **Thinking indicator**: shows the step the agent is really on (the tool it is using) or "Thinking", a timer after 3 seconds, and after 10 seconds "Waking up the server… the first answer of
  the day can take up to a minute".
- **Details form**: now "Get personal help (optional)" with "Skip and see the answer". Skipping
  sends the question straight away and the form is not shown again in that browser session.
- **Errors**: plain messages with the Admissions Office number; Retry no longer sends the question
  twice.
- **Campus visit**: a date in the sentence ("visit campus on 2026-11-25") now goes straight to the
  date confirmation and booking form.
- **Early Bird offer**: hidden by default (`SHOW_EARLY_BIRD_OFFER=false`). The chip now says
  "How to Apply for 2027-28".
- **Accessibility**: keyboard focus outlines; all buttons labelled; tap targets at least 32 px
  (40 px on touch screens); no text under 11 px except the decorative "SRU" badge letters; zoom
  allowed; reduced-motion respected; 16 px form fields on phones (stops iPhone auto-zoom).
- **Smaller fixes**: fee card is a 2×2 grid on phones with a darker, readable green; sidebar "New
  chat" button and logo; "BETA" pill; calculator result heading; meta titles say 2027-28; staff
  console list shows plain text instead of raw markdown.

### Staff and server
- **Admin console is staff-only**: the button is hidden. Staff open it with
  `https://university-ai-companion.vercel.app/#admin` (it still asks for the admin key).
- **Security headers**: the server sends `X-Content-Type-Options`, `Referrer-Policy`,
  `X-Frame-Options: DENY` and, in production, `Strict-Transport-Security`. The site sends
  `X-Content-Type-Options`, `Referrer-Policy` and a `Permissions-Policy` (microphone only for the
  site itself; no camera, location or payment). The site deliberately does not block framing, so it
  can still be embedded on the admission page.
- **Browser access (CORS)**: only listed sites (`CORS_ORIGINS`) or the pattern `CORS_ORIGIN_REGEX`
  (default: localhost and `*.vercel.app`) can call the API; no credentials; errors no longer echo
  unknown sites.
- **Caching**: the site's built files are cached for a year (their names change on every build);
  `index.html` is never cached, so a new release shows up immediately.
- **Chat titles** skip greetings and use the first real question.
- **Keep-awake job**: `.github/workflows/keep-backend-awake.yml` calls `/health` every 10 minutes
  from about 06:30 to 23:30 India time, so the morning's first student does not wait. It does
  nothing until the GitHub variable `BACKEND_URL` is set (see section 4).

## 3. Tests

| Check | Result |
|---|---|
| Backend tests with PostgreSQL | 470 passed, 1 skipped |
| Backend tests without a database | 462 passed, 7 skipped; 2 tests need a database and fail the same way on v2.8.0 |
| Frontend build (TypeScript + Vite) | Passes |
| Fee calculator vs. fee card and backend | 3,477 checks passed (338 backend answers compared) |
| Screen tour, 4 sizes × light/dark | No horizontal scrolling; admin button hidden; no unlabelled buttons |
| Phone with touch emulation | No tap target under 32 px |

New tests: Early Bird off by default; security headers present and unknown sites not echoed;
greetings never become the chat title.

## 4. Before going live (to do on the servers)

1. **Merge** this version and let Vercel and Render redeploy.
2. **Render > Environment**: set a long random `ADMIN_API_KEY` (not `change-me-in-production`),
   `APP_ENV=production`, `APP_DEBUG=false`. Leave `SHOW_EARLY_BIRD_OFFER` unset (off).
3. **Rotate keys**: the Gemini keys and the database password were in the project zip that was
   shared. Create new ones, put them in Render, and delete the old ones.
4. **GitHub > Settings > Secrets and variables > Actions > Variables**: add
   `BACKEND_URL = https://university-ai-luwe.onrender.com` to switch on the keep-awake job.
5. **Optional**: narrow `CORS_ORIGIN_REGEX` to your own site once the final address is fixed.
6. **Check on the live site** (10 minutes): ask a B.Tech CSE fee question with 85% and an EAPCET
   rank; book a campus visit with a date; open `/#admin` and log in; try it on a phone.

## 5. Still for the university to confirm

These are shown carefully or not at all until someone in admissions confirms them:
- Minimum marks for each programme for 2027-28.
- Campus visit hours (the form says 10 AM-4 PM, Mon-Sat).
- The final list of documents to bring.
- Whether an Early Bird / application-fee offer exists for 2027-28 (then set
  `SHOW_EARLY_BIRD_OFFER=true`).

## 6. Not tested here

- The real Gemini model (tests use a stand-in that returns fixed replies; the API was not changed).
- Real phones and Safari (Chrome with phone sizes and touch emulation was used).
- Voice typing with a real microphone.
- Load testing with many students at the same time on the free Render and Gemini tiers.
