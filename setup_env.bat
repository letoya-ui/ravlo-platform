@echo off
title 🚀 Caughman Mason LoanMVP Auto Setup
color 0A
echo.
echo ===============================================
echo   Caughman Mason LoanMVP Setup & Launch Script
echo ===============================================
echo.

REM --- Change working directory ---
cd /d "%~dp0"

echo 🔄 Cleaning up old cache files...
for /r %%i in (__pycache__) do if exist "%%i" rmdir /s /q "%%i"
if exist "venv\Scripts\activate" (
    echo ✅ Virtual environment found.
) else (
    echo ⚙️  Creating new virtual environment...
    py -m venv venv
)

echo.
echo 🔥 Activating virtual environment...
call venv\Scripts\activate

echo.
echo 📦 Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install Flask-Session
pip install flask flask_sqlalchemy flask_login flask_migrate flask_socketio flask_cors
pip install pandas

echo.
echo 🧱 Preparing database...
if not exist "LoanMVP\instance" mkdir LoanMVP\instance
if not exist "LoanMVP\instance\loanmvp.db" (
    echo ⚙️  Initializing new database...
    flask --app LoanMVP.app db init
)
echo ⚙️  Running migrations...
flask --app LoanMVP.app db migrate -m "auto update"
flask --app LoanMVP.app db upgrade

echo.
echo ✅ Database updated.

echo.
echo 🚀 Starting LoanMVP application...
python -m LoanMVP.app

pause
