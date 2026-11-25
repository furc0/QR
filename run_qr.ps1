$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Install Python 3.11+ from https://www.python.org/downloads/" }
if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3 -m venv .venv }
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
Write-Host "Starting QR at http://127.0.0.1:8765" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m uvicorn qr_server.main:app --app-dir server --host 127.0.0.1 --port 8765
