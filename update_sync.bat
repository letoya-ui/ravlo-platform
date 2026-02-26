@echo off
echo === Syncing LoanMVP Stable v1.1 ===
cd %~dp0
git add .
git commit -m "Sync update"
git pull origin main
git push origin main
echo ✅ Sync complete across devices!
pause
