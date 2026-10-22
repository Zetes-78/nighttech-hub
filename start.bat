@echo off
title Night Tech Hub
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 ( set PY=py -3 ) else ( set PY=python )
if not exist ".venv\Scripts\python.exe" (
  echo Setting up for the first time. This takes a minute...
  %PY% -m venv .venv
  if errorlevel 1 ( echo Python was not found. Install it from https://www.python.org/downloads/ and tick "Add Python to PATH". & pause & exit /b 1 )
)
call ".venv\Scripts\activate.bat"
pip install -r requirements.txt --quiet
start "" /min cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"
python run.py
pause
