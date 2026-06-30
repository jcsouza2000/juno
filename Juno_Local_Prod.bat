@echo off
setlocal EnableExtensions EnableDelayedExpansion
title JUNO - Modo Producao Local (sem HMR, botoes funcionam)

REM Auto-elevacao para conseguir liberar portas travadas por processos protegidos
net session >nul 2>&1
if errorlevel 1 (
    echo [INFO] Solicitando privilegios de administrador...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

for %%I in ("%~dp0.") do set "ROOT=%%~fI"
set "BACKEND=%ROOT%\janus\backend"
set "FRONTEND=%ROOT%\janus\frontend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"
set "BACKEND_URL=http://127.0.0.1:8001"
set "FRONTEND_URL=http://127.0.0.1:4000"
set "LOCAL_DB=sqlite:///./smart_juno.db"
set "LOCAL_SECRET_KEY=smart-juno-local-secret-key-must-have-at-least-32-chars"
set "LOCAL_ENCRYPTION_KEY=N6zYqfBC2CxUgdztuLcM5nVSyxe7S6TjzS-ZmrkcmCM="
set "LOCAL_AUTH_SECRET=smart-juno-local-auth-secret-only-for-development-32-chars"
set "LOG_DIR=%ROOT%\logs"

echo ============================================================
echo  JUNO - MODO PRODUCAO LOCAL
echo  Frontend compilado (sem hot-reload) -- corrige a hidratacao
echo  travada que deixava os botoes sem funcionar.
echo ============================================================
echo.

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

echo [1/5] Encerrando processos node antigos...
taskkill /F /IM node.exe >nul 2>&1

echo [2/5] Liberando portas 4000 e 8001...
for %%P in (4000 8001) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do taskkill /F /PID %%A >nul 2>&1
)

echo [3/5] Subindo BACKEND local (SQLite, bypass de login)...
call :free_check
start "JUNO Backend :8001" /D "%BACKEND%" cmd /k "set ""PYTHONPATH=."" && set ""JUNO_ENV=development"" && set ""JUNO_DEV_COMPANY_ID=4"" && set ""DATABASE_URL=%LOCAL_DB%"" && set ""SECRET_KEY=%LOCAL_SECRET_KEY%"" && set ""ENCRYPTION_KEY=%LOCAL_ENCRYPTION_KEY%"" && set ""ALLOWED_ORIGINS=http://localhost:4000,http://127.0.0.1:4000"" && call ""%PY%"" -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload"
echo     Aguardando backend responder...
call :wait_http "%BACKEND_URL%/health" 90 "backend"
if errorlevel 1 ( echo [ERRO] Backend nao subiu. & pause & exit /b 1 )

echo [4/5] COMPILANDO o frontend (build de producao)... isso leva 1-2 min.
pushd "%FRONTEND%"
set "NEXT_PUBLIC_API_URL=%BACKEND_URL%"
set "NEXT_PUBLIC_DEV_COMPANY_ID=4"
set "NEXT_PUBLIC_FALLBACK_API_URL=%BACKEND_URL%"
set "NEXTAUTH_URL=%FRONTEND_URL%"
set "AUTH_SECRET=%LOCAL_AUTH_SECRET%"
set "NEXTAUTH_SECRET=%LOCAL_AUTH_SECRET%"
call npm run build
if errorlevel 1 ( popd & echo [ERRO] Build do frontend falhou. & pause & exit /b 1 )
popd

echo [5/5] Iniciando frontend COMPILADO (sem HMR)...
start "JUNO Frontend PROD :4000" /D "%FRONTEND%" cmd /k "set ""NODE_ENV=production"" && set ""JUNO_LOCAL_NO_AUTH=1"" && set ""NEXT_PUBLIC_API_URL=%BACKEND_URL%"" && set ""NEXT_PUBLIC_DEV_COMPANY_ID=4"" && set ""NEXT_PUBLIC_FALLBACK_API_URL=%BACKEND_URL%"" && set ""NEXTAUTH_URL=%FRONTEND_URL%"" && set ""AUTH_SECRET=%LOCAL_AUTH_SECRET%"" && set ""NEXTAUTH_SECRET=%LOCAL_AUTH_SECRET%"" && call npm run start -- --port 4000"
echo     Aguardando frontend responder...
call :wait_http "%FRONTEND_URL%" 90 "frontend"
if errorlevel 1 ( echo [ERRO] Frontend nao subiu. & pause & exit /b 1 )

echo.
echo ============================================================
echo  PRONTO! Abrindo o dashboard. Os botoes agora funcionam.
echo  IMPORTANTE: abra uma janela ANONIMA nova e va em:
echo     %FRONTEND_URL%/integrations
echo ============================================================
start "" "%FRONTEND_URL%/integrations"
echo Pode fechar esta janela. As janelas Backend/Frontend devem ficar abertas.
pause
exit /b 0

:free_check
exit /b 0

:wait_http
set "WAIT_URL=%~1"
set "WAIT_MAX=%~2"
set "WAIT_NAME=%~3"
set /a WAIT_TRY=0
:wait_http_loop
set /a WAIT_TRY+=1
if !WAIT_TRY! GTR %WAIT_MAX% exit /b 1
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%WAIT_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 exit /b 0
if "!WAIT_TRY!"=="1" echo     [INFO] aguardando %WAIT_NAME%...
timeout /t 2 /nobreak >nul
goto wait_http_loop
