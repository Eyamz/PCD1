@echo off
echo ============================================================
echo Tunisian Proverbs - Web Application Launcher
echo ============================================================
echo.

REM Check if venv exists
if not exist ".venv" (
    echo Virtual environment not found. Creating...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing requirements...
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo ============================================================
echo Starting FastAPI Server...
echo ============================================================
echo.
echo Visit: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

python run.py

pause
