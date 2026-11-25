$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PythonLauncher) {
    throw "Python 3.11 or newer with the Windows Python Launcher is required. Install it from https://www.python.org/downloads/ and enable the Python Launcher."
}

& py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "A working Python 3.11 or newer installation was not found. Install Python 3.11+ and try again."
}

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# A copied virtual environment may retain an absolute path to Python on another PC.
# Test it first; if it is broken, rebuild only .venv. User data is stored separately in data/.
if (Test-Path $VenvPython) {
    & $VenvPython -c "import sys" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "The existing .venv is not valid on this computer. Recreating it..."
        Remove-Item -LiteralPath (Join-Path $PSScriptRoot ".venv") -Recurse -Force
    }
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating a local Python environment..."
    & py -3 -m venv (Join-Path $PSScriptRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create .venv. Check that Python 3.11+ is installed correctly."
    }
}

& $VenvPython -c "import sys"
if ($LASTEXITCODE -ne 0) {
    throw "The virtual environment cannot start. Check your Python installation."
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not prepare pip." }

& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

& $VenvPython install_step_runtime.py
$env:PYTHONPATH = Join-Path $PSScriptRoot "server"
& $VenvPython -m qr_server.launcher
exit $LASTEXITCODE
