@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 or newer with the Windows Python Launcher is required.
    echo Install it from https://www.python.org/downloads/ and enable the Python Launcher.
    pause
    exit /b 1
)

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo A working Python 3.11 or newer installation was not found.
    echo Install Python 3.11+ and try again.
    pause
    exit /b 1
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"

rem A copied virtual environment may contain an absolute path to Python on another PC.
rem Validate its interpreter and rebuild only .venv when it is broken.
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys" >nul 2>nul
    if errorlevel 1 (
        echo The existing .venv is not valid on this computer. Recreating it...
        rmdir /s /q "%CD%\.venv"
    )
)

if not exist "%VENV_PY%" (
    echo Creating a local Python environment...
    py -3 -m venv "%CD%\.venv"
    if errorlevel 1 (
        echo Could not create .venv. Check that Python 3.11+ is installed correctly.
        pause
        exit /b 1
    )
)

"%VENV_PY%" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo The new virtual environment cannot start. Check your Python installation.
    pause
    exit /b 1
)

"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo Could not prepare pip.
    pause
    exit /b 1
)

"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

"%VENV_PY%" install_step_runtime.py
set "PYTHONPATH=%CD%\server"
"%VENV_PY%" -m qr_server.launcher
if errorlevel 1 echo QR server stopped with an error.
pause
