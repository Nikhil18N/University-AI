#!/usr/bin/env zsh
# University AI Companion — macOS Launcher
# Usage: chmod +x start.sh && ./start.sh

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

export PATH="/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

SCRIPT_DIR="${0:A:h}"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "${CYAN}========================================================"
echo "       Starting University AI Companion System"
echo "========================================================${NC}"

# ── 1. Docker ─────────────────────────────────────────────────────────────────
echo "\n${YELLOW}[1/4] Checking Docker containers...${NC}"
if ! command -v docker &>/dev/null; then
  echo "${RED}[ERROR] Docker is not installed. Install Docker Desktop from https://www.docker.com/products/docker-desktop/${NC}"
  exit 1
fi
if ! docker info &>/dev/null; then
  echo "${RED}[ERROR] Docker daemon is not running. Please start Docker Desktop first.${NC}"
  exit 1
fi
echo "${GREEN}Starting Docker containers (PostgreSQL, ChromaDB, Redis)...${NC}"
docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d
echo "${GREEN}Docker containers are up.${NC}"

# ── 2. Ollama (if configured) ──────────────────────────────────────────────────
echo "\n${YELLOW}[2/4] Checking Ollama server...${NC}"
USES_OLLAMA=false
if [ -f "$BACKEND_DIR/.env" ]; then
  if grep -E "^(LLM_PROVIDER|EMBEDDING_PROVIDER)=ollama" "$BACKEND_DIR/.env" &>/dev/null; then
    USES_OLLAMA=true
  fi
else
  USES_OLLAMA=true
fi

if [ "$USES_OLLAMA" = true ]; then
  if ! command -v ollama &>/dev/null; then
    echo "${RED}[ERROR] Ollama is not installed. Install it with: brew install ollama${NC}"
    exit 1
  fi
  if curl -s --max-time 2 http://localhost:11434/api/tags &>/dev/null; then
    echo "${GREEN}Ollama server is already running.${NC}"
  else
    echo "${YELLOW}Starting Ollama server in background...${NC}"
    ollama serve &>/tmp/ollama.log &
    sleep 3
    echo "${GREEN}Ollama server started (log: /tmp/ollama.log).${NC}"
  fi
else
  echo "${GREEN}Cloud provider configured (Gemini/OpenRouter) — skipping local Ollama check.${NC}"
fi

# ── 3. Backend ────────────────────────────────────────────────────────────────
echo "\n${YELLOW}[3/4] Starting FastAPI backend (port 8080)...${NC}"
if [ ! -d "$BACKEND_DIR/venv" ]; then
  echo "${YELLOW}Virtual environment not found — creating one...${NC}"
  /opt/homebrew/bin/python3.11 -m venv "$BACKEND_DIR/venv"
  source "$BACKEND_DIR/venv/bin/activate"
  pip install --upgrade pip -q
  pip install -r "$BACKEND_DIR/requirements.txt" -q
  echo "${GREEN}Dependencies installed.${NC}"
fi

# Copy .env if it doesn't exist
if [ ! -f "$BACKEND_DIR/.env" ]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "${YELLOW}Created backend/.env from .env.example — edit it to set your API keys.${NC}"
fi

osascript -e "tell application \"Terminal\" to do script \"
  source '$BACKEND_DIR/venv/bin/activate'
  cd '$BACKEND_DIR'
  python -m alembic upgrade head 2>/dev/null || true
  uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
\""

# ── 4. Frontend ───────────────────────────────────────────────────────────────
echo "\n${YELLOW}[4/4] Starting React frontend (port 5173)...${NC}"
if ! command -v node &>/dev/null; then
  echo "${RED}[ERROR] Node.js is not installed. Install it with: brew install node${NC}"
  exit 1
fi
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "${YELLOW}Installing frontend dependencies...${NC}"
  cd "$FRONTEND_DIR" && npm install -q
fi

osascript -e "tell application \"Terminal\" to do script \"
  cd '$FRONTEND_DIR'
  npm run dev
\""

echo "\n${GREEN}========================================================"
echo "All services are launching in separate Terminal windows!"
echo "  - Student Chat:     http://localhost:5173"
echo "  - Admin Dashboard:  http://localhost:5173 (Click Admin button)"
echo "  - Backend API Docs: http://localhost:8080/docs"
echo "  - Admin API Key:    change-me-in-production (set in backend/.env)"
echo "========================================================${NC}\n"

