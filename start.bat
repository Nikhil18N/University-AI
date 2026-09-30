@echo off
title University AI Companion Launcher
echo ========================================================
echo        Starting University AI Companion System
echo ========================================================
echo.

:: 1. Check Docker
echo [1/4] Checking Docker containers...
docker ps >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Docker Desktop does not appear to be running.
    echo Please start Docker Desktop and run: docker compose up -d
    echo.
) else (
    echo Starting Docker containers (PostgreSQL, ChromaDB, Redis)...
    docker compose up -d
)

:: 2. Check Ollama
echo [2/4] Starting Ollama server...
start "Ollama Server" cmd /k "ollama serve"

:: 3. Start Backend
echo [3/4] Starting FastAPI backend (port 8080)...
start "FastAPI Backend" cmd /k "cd /d %~dp0backend && .\venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"

:: 4. Start Frontend
echo [4/4] Starting React Frontend (port 5173)...
start "Frontend Dev Server" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================================
echo All services are launching!
echo.
echo - Student Chat:     http://localhost:5173
echo - Admin Dashboard:  http://localhost:5173 (Click Admin button)
echo - Backend API Docs: http://localhost:8080/docs
echo - Admin API Key:    change-me-in-production
echo ========================================================
echo.
pause
