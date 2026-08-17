# Starts the local half of the deployed setup, each part in its own console
# window: the Cloud SQL Auth Proxy, the dispatcher, and the ARQ worker.
#
# The API and UI run on Cloud Run and only write DiscoveryJob rows; the
# dispatcher claims those rows and enqueues them into the local Redis this
# worker consumes. Scraping stays here so it runs from a residential IP.
#
# Separate processes on purpose - a Playwright/Chromium crash in the worker
# must not take down dispatching, and vice versa. Same pattern as dev.ps1.

$backendRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"
$envFile = Join-Path $backendRoot ".env.production"
$proxyExe = Join-Path $PSScriptRoot "cloud-sql-proxy.x64.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Venv not found at $venvPython - create it first (python -m venv .venv && pip install -r requirements.txt)"
    exit 1
}

if (-not (Test-Path $envFile)) {
    Write-Error "$envFile not found - copy .env.production.example to .env.production and fill it in"
    exit 1
}

if (-not (Test-Path $proxyExe)) {
    Write-Error "Cloud SQL Auth Proxy not found at $proxyExe - download cloud-sql-proxy.x64.exe into backend\scripts\ (it is gitignored)"
    exit 1
}

# The instance connection name lives in .env.production so there is a single
# place to configure this machine, rather than a second copy in this script.
$connectionName = (Select-String -Path $envFile -Pattern '^\s*CLOUD_SQL_CONNECTION_NAME\s*=\s*(.+?)\s*$' |
    Select-Object -First 1).Matches.Groups[1].Value

if ([string]::IsNullOrWhiteSpace($connectionName)) {
    Write-Error "CLOUD_SQL_CONNECTION_NAME is not set in $envFile (expected project:region:instance)"
    exit 1
}

# 5433, not 5432: the local Postgres install already owns 5432.
Start-Process -WorkingDirectory $backendRoot -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "& '$proxyExe' --port 5433 '$connectionName'"

# The proxy needs a moment to authenticate and start listening. Without this
# the dispatcher's first few polls just log connection errors - harmless, since
# it retries, but noisy enough to look like a real failure.
Start-Sleep -Seconds 3

# ENV_FILE is what makes both processes read .env.production instead of .env
# (see get_settings() in app/core/config.py). Set inside each child window
# because Start-Process spawns a fresh PowerShell that does not inherit it.
Start-Process -WorkingDirectory $backendRoot -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "`$env:ENV_FILE='.env.production'; & '$venvPython' -m app.workers.dispatcher"

Start-Process -WorkingDirectory $backendRoot -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "`$env:ENV_FILE='.env.production'; & '$venvPython' -m arq app.workers.queue.WorkerSettings"

Write-Host "Started Cloud SQL Auth Proxy (127.0.0.1:5433), dispatcher, and ARQ worker in separate windows."
Write-Host "Close a window to stop that process. Stop a running discovery from the UI first - stop is cooperative."
