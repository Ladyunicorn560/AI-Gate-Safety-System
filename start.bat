@echo off
title AI Gate Safety System
color 0A
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║        AI Gate Safety System — Starting...          ║
echo  ║   Face Recognition + PPE Detection Dashboard        ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if DB needs setup
echo [1/3] Checking database...
python -c "from backend.database.schema import setup; setup()" 2>nul
if %errorlevel% neq 0 (
    echo  [!] DB setup warning - continuing anyway
)

echo [2/3] Starting Flask server...
echo.
echo  Dashboard: http://localhost:5000
echo  Press Ctrl+C to stop
echo.

REM Start the application
python -m backend.app

pause
