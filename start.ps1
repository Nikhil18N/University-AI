# University AI Companion Launcher
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       Starting University AI Companion System" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Docker check
Write-Host "`n[1/4] Checking Docker containers..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "Starting Docker containers (PostgreSQL, ChromaDB, Redis)..." -ForegroundColor Green
    docker compose up -d
} catch {
    Write-Host "[WARNING] Docker Desktop is not running or not responding." -ForegroundColor Red
    Write-Host "Please start Docker Desktop manually and run: docker compose up -d" -ForegroundColor Yellow
}

# 2. Ollama
Write-Host "`n[2/4] Checking Ollama server (required for RAG embeddings)..." -ForegroundColor Yellow
$ollamaRunning = $false
try {
    $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
    $ollamaRunning = $true
    Write-Host "Ollama server is already running and ready." -ForegroundColor Green
} catch {
    Write-Host "Starting Ollama server..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "ollama serve"
    Start-Sleep -Seconds 3
}

# 3. Backend
Write-Host "`n[3/4] Starting FastAPI backend (port 8080)..." -ForegroundColor Yellow
$backendDir = Join-Path $PSScriptRoot "backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$backendDir'; .\venv\Scripts\Activate.ps1; uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"

# 4. Frontend
Write-Host "`n[4/4] Starting React Frontend (port 5173)..." -ForegroundColor Yellow
$frontendDir = Join-Path $PSScriptRoot "frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; npm run dev"

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "All services are launching in separate terminal windows!" -ForegroundColor Green
Write-Host "  - Student Chat:     http://localhost:5173" -ForegroundColor White
Write-Host "  - Admin Dashboard:  http://localhost:5173 (Click Admin button)" -ForegroundColor White
Write-Host "  - Backend API Docs: http://localhost:8080/docs" -ForegroundColor White
Write-Host "  - Admin API Key:    change-me-in-production" -ForegroundColor White
Write-Host "========================================================`n" -ForegroundColor Green
