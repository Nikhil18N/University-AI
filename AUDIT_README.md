# Read me first: version 2.8.0 (audit round 2, 17 Nov 2026)

This delivery is built on **v2.7.0**, the version you already merged and that is live.
Every earlier feature is kept.

**What to read:** `docs/25-audit-round-2-nov-2026.md` (what was wrong, what changed, what was
checked on sru.edu.in, what the university has to decide).

## What is in the zip

| In the zip | What it is | Use it when |
|---|---|---|
| `CHANGES_ONLY/` | Only the files added or changed since v2.7.0, in their folders | **Easiest merge:** copy this folder over your project and say "replace" |
| `audit-round2.patch` | The same changes as a git patch against v2.7.0 | You prefer `git apply --3way audit-round2.patch` on a new branch |
| `University-AI/` | The complete project, clean (no `venv`, `node_modules`, build output, secret files) | You want to compare, or start from this copy |

If you changed any of the same files yourselves after merging v2.7.0, use the patch with
`--3way` (git shows you the conflicts) instead of copying over.

Your own `.env` files are not in the zip. No new setting is required; optional ones are at the
end of `backend/.env.example`. No database migration is needed.

## After merging

```bash
cd backend
pip install -r requirements.txt
python scripts/export_fee_config.py     # regenerates the calculator copy and the handbook fee pages
pytest                                  # 467 pass with PostgreSQL running

cd ../frontend
npm install
npm test                                # 3,477 checks
npm run build
```

Then deploy backend (Render) and frontend (Vercel) as usual, and run the six-line check in
section 5 of `docs/25-audit-round-2-nov-2026.md`.

## To change a fee later

Edit `backend/app/sru_agent/fees_2027_28.json` only, then run
`python scripts/export_fee_config.py` in `backend/`. The chat, the calculator, the fee cards
and the handbook pages all come from that one file. Tests fail if you forget.

## To add knowledge

Put a `.md` file in `backend/data/handbook/` **and** the same file in `data/handbook/`, add it to
`HANDBOOK_DOCS` in `backend/scripts/ingest_handbook_docs.py`, and restart. The agent reads it at once.
