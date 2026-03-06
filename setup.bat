@echo off
REM Development setup script for Windows

echo 🚀 AI Agents SaaS Platform - Development Setup
echo ================================================

REM Check Python version
echo ✓ Checking Python version...
python --version

REM Create virtual environment
if not exist "venv" (
    echo ✓ Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo ✓ Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo ✓ Installing dependencies...
pip install -r requirements.txt

REM Initialize database
echo ✓ Initializing database...
python init_db.py

echo.
echo ✅ Setup complete!
echo.
echo Next steps:
echo 1. Copy .env.example to .env and update configuration
echo 2. Run: uvicorn app.main:app --reload
echo 3. Visit: http://localhost:8000
echo.
