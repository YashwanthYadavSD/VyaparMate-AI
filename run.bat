@echo off
title VyaparMate AI
cd /d "%~dp0"
echo ======================================
echo        VyaparMate AI - Launcher
echo ======================================
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment. Install Python 3.11 or newer and try again.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check your internet connection and try again.
  pause
  exit /b 1
)
echo Starting VyaparMate AI at http://127.0.0.1:8000
echo Press Ctrl+C to stop.
python -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
