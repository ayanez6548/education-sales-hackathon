$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"
$py = "$Root\.venv\Scripts\python.exe"
& $py -m pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Set-Location "$Root\frontend"
npm run typecheck
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build
exit $LASTEXITCODE
