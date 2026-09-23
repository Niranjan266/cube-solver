@echo off
REM  Rubik's Cube Solver - one-click start (Windows)
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Creating a virtual environment...
  python -m venv .venv || goto :fail
)

call .venv\Scripts\activate.bat

echo Installing dependencies (first run only, takes a minute)...
python -m pip install --upgrade pip >nul
python -m pip install -r backend\requirements.txt || goto :fail

echo.
echo ==========================================================
echo   Cube Solver is starting.
echo   Open  http://127.0.0.1:8000  in your browser.
echo   Press Ctrl+C here to stop it.
echo ==========================================================
echo.

cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000
if %errorlevel% neq 0 pause
goto :eof

:fail
echo.
echo Something went wrong. Make sure Python 3.9+ is installed and on your PATH.
pause
