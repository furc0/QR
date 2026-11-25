@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Install Python 3.11+ from https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (echo Dependency installation failed & pause & exit /b 1)
python install_step_runtime.py
set "PYTHONPATH=%CD%\server"
python -m qr_server.launcher
if errorlevel 1 (echo QR server stopped with an error.)
pause
