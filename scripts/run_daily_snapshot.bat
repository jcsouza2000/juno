@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\janus\backend\.venv\Scripts\python.exe"
set "LOG=%ROOT%\logs\daily-snapshot.log"
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
cd /d "%ROOT%\janus\backend"
set PYTHONPATH=.
set DATABASE_URL=sqlite:///./smart_juno.db
set JUNO_ENV=development
set SECRET_KEY=smart-juno-local-secret-key-must-have-at-least-32-chars
set ENCRYPTION_KEY=N6zYqfBC2CxUgdztuLcM5nVSyxe7S6TjzS-ZmrkcmCM=
echo [%date% %time%] daily snapshot >> "%LOG%"
"%PY%" "%ROOT%\scripts\daily_snapshot_job.py" >> "%LOG%" 2>&1
