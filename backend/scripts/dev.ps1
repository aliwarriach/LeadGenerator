# Starts the API and the ARQ worker together for local dev, each in its own
# console window. Two separate processes on purpose — a Playwright/Chromium
# crash in the worker shouldn't take the API down, and vice versa.

$backendRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Venv not found at $venvPython — create it first (python -m venv .venv && pip install -r requirements.txt)"
    exit 1
}

Start-Process -WorkingDirectory $backendRoot -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "& '$venvPython' -m uvicorn app.main:app --reload --port 8000"

Start-Process -WorkingDirectory $backendRoot -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "& '$venvPython' -m arq app.workers.queue.WorkerSettings"

Write-Host "Started API (http://127.0.0.1:8000) and ARQ worker in separate windows. Close either window to stop it."
