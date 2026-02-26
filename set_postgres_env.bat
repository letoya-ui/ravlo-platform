@echo off
REM ============================================
REM LoanMVP PostgreSQL Environment Setup Script
REM ============================================

echo 🔧 Setting up PostgreSQL environment variables...

REM === Your PostgreSQL Connection Settings ===
set PGUSER=postgres
set PGPASSWORD=Cmrloans2025
set PGHOST=localhost
set PGPORT=5432
set PGDATABASE=loanmvp_db

REM === Flask Environment Variables ===
set FLASK_APP=LoanMVP.app
set FLASK_ENV=development

REM === SQLAlchemy Database URL ===
set DATABASE_URL=postgresql+psycopg2://%PGUSER%:%PGPASSWORD%@%PGHOST%:%PGPORT%/%PGDATABASE%

echo ✅ PostgreSQL configuration loaded successfully!
echo.
echo 🚀 You can now run Flask commands like:
echo     flask --app LoanMvp.app db upgrade
echo     python -m LoanMVP.app
echo.

cmd /k
