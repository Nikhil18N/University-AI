# Read me first: version 2.9.0 (production readiness, 17 Nov 2026)

This delivery is built on **v2.8.0** (commit `5314637`). Every earlier feature is kept and the
free Gemini API is unchanged.

**What to read:** `docs/26-production-readiness-nov-2026.md` (what was found, what changed, the
six steps to do on the servers before going live, and what the university still has to confirm).
The previous round is in `docs/25-audit-round-2-nov-2026.md`.

## What is in the zip

| In the zip | What it is | Use it when |
|---|---|---|
| `CHANGES_ONLY/` | Only the files added or changed since v2.8.0, in their folders | **Easiest merge:** copy this folder over your project and say "replace" |
| `audit-round3.patch` | The same changes as a git patch against v2.8.0 | You prefer `git apply --3way audit-round3.patch` on a new branch |
| `University-AI/` | The complete project, clean (no `venv`, `node_modules`, build output, secret files) | You want to compare, or start from this copy |

If you changed any of the same files yourselves after merging v2.8.0, use the patch with
`--3way` (git shows you the conflicts) instead of copying over.

Your own `.env` files are not in the zip. No database migration is needed. New optional settings
(`SHOW_EARLY_BIRD_OFFER`, `CORS_ORIGIN_REGEX`) are in `backend/.env.example`; their defaults are
right for production.

## After merging

```bash
cd backend
pip install -r requirements.txt
pytest                                  # 470 pass with PostgreSQL running

cd ../frontend
npm install
npm test                                # 3,477 checks
npm run build
```

Then deploy backend (Render) and frontend (Vercel) as usual and follow section 4 of
`docs/26-production-readiness-nov-2026.md`.

## Staff: the admin console

The admin button is no longer shown to students. Staff open
`https://university-ai-companion.vercel.app/#admin` and log in with the admin key.

## To change a fee later

Edit `backend/app/sru_agent/fees_2027_28.json` only, then run
`python scripts/export_fee_config.py` in `backend/`. The chat, the calculator, the fee cards
and the handbook pages all come from that one file. Tests fail if you forget.

## To add knowledge

Put a `.md` file in `backend/data/handbook/` **and** the same file in `data/handbook/`, add it to
`HANDBOOK_DOCS` in `backend/scripts/ingest_handbook_docs.py`, and restart. The agent reads it at once.
