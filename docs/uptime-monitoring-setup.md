# Uptime Monitoring Setup (Render Cold Start Prevention)

## Problem
Render's free tier spins down backend web services after 15 minutes of inactivity. The first request after an idle period incurs a **15–50 second cold start delay** (container boot + Python module import + ChromaDB index loading).

## Solution: External Uptime Ping (Free)

An external HTTP ping every 5 to 10 minutes keeps the Render instance warm 24/7 without requiring code modifications or server-side crons.

### Setup Instructions with UptimeRobot (Recommended)

1. Sign up for a free account at [UptimeRobot](https://uptimerobot.com).
2. Click **+ Add New Monitor**.
3. Fill in the monitor settings:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `SRU Buddy Backend (Keep Warm)`
   - **URL (or IP)**: `https://<your-render-backend-url>.onrender.com/api/health`
   - **Monitoring Interval**: `5 minutes` or `10 minutes` (free tier supports 5-min intervals)
   - **HTTP Method**: `HEAD` or `GET`
4. Click **Create Monitor**.

### How It Works
- Every 5–10 minutes, UptimeRobot requests `/api/health`.
- The health check runs in memory and responds in < 10ms.
- Render resets its 15-minute idle countdown timer on every ping, preventing the container from spinning down.

## Upgrading to Render Paid Plan (Long-Term Production)

For enterprise-grade reliability and zero cold starts:
- Upgrade the backend web service to Render's **Starter tier ($7/month)**.
- Starter tier services do not spin down when idle.
- Provides persistent disk support, ensuring ChromaDB document embeddings in `chroma_data/` survive deploys and restarts.
