$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Install Python 3.11+ from https://www.python.org/downloads/" }
if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3 -m venv .venv }
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& ".venv\Scripts\python.exe" "install_step_runtime.py"
$env:PYTHONPATH = Join-Path $PSScriptRoot "server"
& ".venv\Scripts\python.exe" -m qr_server.launcher
exit $LASTEXITCODE
