$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Error "No existe .venv en la raiz. Creala con: py -3.14 -m venv .venv"
}

$env:APP_ENV = "demo"
$env:DEMO_MODE = "true"
$env:EMBED_WORKER = "true"
$env:TELEGRAM_ADAPTER = "demo"
$env:LLM_ADAPTER = "demo"
$env:AUTH_ADAPTER = "demo"
$env:PYTHONPATH = "$Root\backend"

if (-not $env:DATABASE_URL) {
  $dbPath = "$Root\data\education_sales_demo.db" -replace "\\", "/"
  $env:DATABASE_URL = "sqlite+pysqlite:///$dbPath"
  Write-Host "Docker no es necesario para esta demo. Usando SQLite en $dbPath"
}

New-Item -ItemType Directory -Force -Path "$Root\data" | Out-Null
Write-Host "API en http://localhost:8000  (adaptadores SIMULADOS)"
Write-Host "Arranca el frontend en otra terminal: cd frontend; npm install; npm run dev"
Set-Location "$Root\backend"
& "$Root\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 3
