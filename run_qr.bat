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
echo QR is starting at http://127.0.0.1:8765
echo Keep this window open. Runtime data is stored in the data folder.
python -m uvicorn qr_server.main:app --app-dir server --host 127.0.0.1 --port 8765
pause
