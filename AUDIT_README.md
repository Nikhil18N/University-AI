# Read me first: audited version 2.7.0 (17 Nov 2026)

This folder is the SRU Buddy project after a full audit. Every earlier feature is kept.

**What to read:** `docs/24-agent-audit-nov-2026.md` (what was wrong, what changed, how to deploy,
what the university still has to confirm).

## How to use this delivery

You received one zip with three things:

| In the zip | What it is | Use it when |
|---|---|---|
| `University-AI/` | The complete project, clean (no `venv`, `node_modules`, build output or secret files) | You want to start from this copy |
| `CHANGES_ONLY/` | Only the 35 files that were added or changed, in their folders | You want to copy the changes over your own working copy |
| `audit-changes.patch` | The same changes as a git patch against commit `bc25aeb` | You prefer `git apply audit-changes.patch` on a new branch |

Your own `.env` files are **not** in the zip (they contain passwords). Keep using the ones on your
machine, and add the new settings listed at the bottom of `backend/.env.example`.

## After copying

```bash
# backend
cd backend
pip install -r requirements.txt
pytest                      # 431 pass with PostgreSQL running

# frontend
cd ../frontend
npm install
npm test                    # calculator checked against the backend, 3,438 checks
npm run build
```

## Three things only you can do

1. **Change the passwords and keys** that were inside the zip you shared (Gemini key, database
   password, Redis URL, admin key, Vercel token). Treat them as exposed.
2. **Gemini capacity:** put several keys from separate Google projects in `GEMINI_API_KEYS`, or
   move to a paid tier. The code now uses every key and retries, but it cannot create quota.
3. **Confirm the nine points** in section 5 of `docs/24-agent-audit-nov-2026.md` with the
   Admissions Office.

## To change a fee later

Edit `backend/app/sru_agent/fees_2027_28.json` only. Then:

```bash
cd backend && python scripts/export_fee_config.py && pytest
cd ../frontend && npm test && npm run build
```

The chat, the calculator and the fee cards all read that one file.
