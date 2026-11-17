# Read me first: version 3.0.0 (admissions brief, 17 Nov 2026)

This delivery is built on **v2.9.0** (commit `3665fe3`). Every earlier feature is kept, except
campus visit *booking*, which the brief asked to remove. The free Gemini API is unchanged.

**What to read:** `docs/27-admissions-brief-nov-2026.md`: what changed for each of the eight
points of the brief, the speed measurements, how to add the widget to a page, and what the
Admissions Office still has to confirm. Earlier rounds: docs 24, 25 and 26.

## What is in the zip

| In the zip | What it is | Use it when |
|---|---|---|
| `CHANGES_ONLY/` | Only the files added or changed since v2.9.0, in their folders | **Easiest merge:** copy this folder over your project and say "replace" |
| `audit-round4.patch` | The same changes as a git patch against v2.9.0 | You prefer `git apply --3way audit-round4.patch` on a new branch |
| `University-AI/` | The complete project, clean (no `venv`, `node_modules`, build output, secret files) | You want to compare, or start from this copy |
| `REMOVED_FILES.txt` | Files to delete after copying `CHANGES_ONLY/` (if any) | Only with the copy method |

If you changed any of the same files yourselves after merging v2.9.0, use the patch with
`--3way` (git shows you the conflicts) instead of copying over.

Your own `.env` files are not in the zip. No database migration is needed. New optional settings
are at the end of `backend/.env.example`; their defaults are right for production. **Check that
Render does not still set `AGENT_RETRY_DELAYS=1.5,4,8`** (delete it or set `1,2.5`).

## After merging

```bash
cd backend
pip install -r requirements.txt
pytest                                  # 511 pass with PostgreSQL running

cd ../frontend
npm install
npm test                                # 3,477 checks
npm run build
```

Deploy backend (Render) and frontend (Vercel) as usual, then follow section 11 of
`docs/27-admissions-brief-nov-2026.md`.

## The widget

One line on any page, just before `</body>`:

```html
<script src="https://university-ai-companion.vercel.app/widget.js" defer></script>
```

Demo: `https://university-ai-companion.vercel.app/widget-demo.html`.

## Staff: the admin console

Open `https://university-ai-companion.vercel.app/#admin` and log in with the admin key.

## To refresh the faculty list

```bash
cd backend
pip install beautifulsoup4
python scripts/fetch_faculty_directory.py data/faculty_raw/sru_faculty_new.json
python scripts/build_faculty_directory.py data/faculty_raw/sru_faculty_new.json
```

## To change a fee later

Edit `backend/app/sru_agent/fees_2027_28.json` only, then run
`python scripts/export_fee_config.py` in `backend/`. The chat, the calculator, the fee cards
and the handbook pages all come from that one file. Tests fail if you forget.

## To add knowledge

Put a `.md` file in `backend/data/handbook/` **and** the same file in `data/handbook/`, add it to
`HANDBOOK_DOCS` in `backend/scripts/ingest_handbook_docs.py`, and restart. The agent reads it at once.
