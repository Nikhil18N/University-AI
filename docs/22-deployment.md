# Deployment & Branching Strategy

## GitHub Branch Separation
To separate production and development safely:

| Branch | Environment | Purpose | Deployment Trigger |
| :--- | :--- | :--- | :--- |
| **`main`** | **Production** | Stable, thoroughly tested code deployed to students. | Auto-deploys to Render & Vercel Production. |
| **`develop`** | **Development** | Active day-to-day integration branch for new features, experiments, and PRs. | Local dev or Render/Vercel Staging/Preview. |

### Development Workflow:
1. Create feature branches off `develop` (e.g. `feat/attendance-calculator`, `fix/chat-scroll`).
2. Test locally against `develop`.
3. Open a Pull Request into `develop` and merge after review.
4. When ready for a production release, merge `develop` into `main`.

## Environments
Development -> Staging -> Production

## Recommended containers
- frontend
- backend
- postgres
- redis
- chromadb/vector service as selected
- ollama/local model service where appropriate

## Configuration
Use environment variables/secrets management.

Required examples:
LLM_PROVIDER
LLM_BASE_URL
LLM_MODEL
DATABASE_URL
REDIS_URL
JWT_SECRET

## Production
- HTTPS
- Backups
- Health checks
- Monitoring
- Log aggregation
- Resource limits
- Database migrations
- Rollback plan

## 100% Free Deployment Guide

### Frontend on Vercel
- **Root Directory**: `frontend`
- **Framework Preset**: Vite
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Environment Variable**: `VITE_API_BASE_URL` = `<your-backend-url>`
- **Routing**: Handled by [frontend/vercel.json](file:///home/mahesh/Documents/University-AI/frontend/vercel.json) rewrites.

### Backend Hosting Options (Free Tier)
1. **Render.com (Free Web Service)**:
   - Deploy backend using the included [backend/Dockerfile](file:///home/mahesh/Documents/University-AI/backend/Dockerfile).
   - Set environment variable `PORT=8080`.
   - Set `CHROMA_PERSIST_DIR=./chroma_data` for embedded persistent vector storage.
2. **Neon.tech (Free Serverless PostgreSQL)**:
   - Provides free `DATABASE_URL` (`postgresql+asyncpg://...`).
3. **Upstash (Free Serverless Redis)**:
   - Provides free `REDIS_URL` (`rediss://...`).
4. **Cloudflare Tunnel / ngrok (Tunnel Local Backend to Vercel)**:
   - Run existing Docker containers + Ollama locally.
   - Run `cloudflared tunnel --url http://localhost:8080` or `ngrok http 8080` to get a free HTTPS URL.
   - Set `VITE_API_BASE_URL` in Vercel to that tunnel URL.
