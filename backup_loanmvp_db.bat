@echo off
setlocal
set PGPASSWORD=Cmrloans2025

:: Backup directory
set BACKUP_DIR=C:\LoanMVP_Bundle\Backups
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

:: Timestamp for file name
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do (set DATESTAMP=%%c-%%a-%%b)
for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set TIMESTAMP=%%a%%b)

:: Run pg_dump
echo 🔄 Backing up loanmvp_db ...
"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -U postgres -F c -b -v -f "%BACKUP_DIR%\loanmvp_db_%DATESTAMP%_%TIMESTAMP%.backup" loanmvp_db

echo ✅ Backup completed! File saved in %BACKUP_DIR%
pause
endlocal
