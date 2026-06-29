@echo off
setlocal EnableExtensions EnableDelayedExpansion
title JUNO Industrial Diagnostic - Launcher

REM === Auto-elevacao: garante privilegio de admin para a limpeza total ===
REM Backends antigos podem subir protegidos e resistir ao Stop-Process comum;
REM so com privilegio elevado o taskkill /F consegue derruba-los.
net session >nul 2>&1
if errorlevel 1 (
    echo [INFO] Solicitando privilegios de administrador para limpar processos...
    if "%~1"=="" (
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    ) else (
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
    )
    exit /b
)

for %%I in ("%~dp0.") do set "ROOT=%%~fI"

set "BACKEND=%ROOT%\janus\backend"
set "FRONTEND=%ROOT%\janus\frontend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"
set "PIP=%BACKEND%\.venv\Scripts\pip.exe"
set "COMPOSE_FILE=%ROOT%\docker-compose.prod.yml"
set "ENV_PROD=%ROOT%\.env.prod"
set "BACKEND_URL=http://127.0.0.1:8001"
set "FRONTEND_URL=http://127.0.0.1:4000"
set "DASHBOARD_URL=%FRONTEND_URL%/executive"
set "LOCAL_DB=sqlite:///./smart_juno.db"
set "LOCAL_SECRET_KEY=smart-juno-local-secret-key-must-have-at-least-32-chars"
set "LOCAL_ENCRYPTION_KEY=N6zYqfBC2CxUgdztuLcM5nVSyxe7S6TjzS-ZmrkcmCM="
REM Modelo do Coordinator (IA). qwen3:8b suporta tool-calling. Para acelerar em
REM maquinas com GPU/modelo menor, troque aqui (ex: llama3.2:3b se suportar tools).
set "JUNO_AI_MODEL=qwen3:8b"
set "LOCAL_AUTH_SECRET=smart-juno-local-auth-secret-only-for-development-32-chars"
set "LOG_DIR=%ROOT%\logs"
set "BACKEND_LOG=%LOG_DIR%\backend-smart-juno.log"
set "FRONTEND_LOG=%LOG_DIR%\frontend-smart-juno.log"
set "FORCE_DOCKER=0"
if /i "%~1"=="docker" set "FORCE_DOCKER=1"

REM === Limpeza total das instancias anteriores (todos os modos exceto 'verificar') ===
if /i not "%~1"=="verificar" call :kill_all

REM === 'reset': limpa o cache do Turbopack (.next) -- forca rebuild do frontend
REM com .env.local e proxy.ts atualizados. Use quando trocar URL/host/env. ===
if /i "%~1"=="reset" call :clear_next

if /i "%~1"=="clean" call :free_ports
if /i "%~1"=="verificar" goto verify_mode
if /i "%~1"=="local" goto local_mode

echo.
echo ============================================================
echo  JUNO Industrial Diagnostic
echo  Launcher inteligente do dashboard
echo ============================================================
echo.

echo [1/5] Validando arquivos do projeto...
if not exist "%BACKEND%" (
    echo [ERRO] Backend nao encontrado em: %BACKEND%
    pause & exit /b 1
)
if not exist "%FRONTEND%" (
    echo [ERRO] Frontend nao encontrado em: %FRONTEND%
    pause & exit /b 1
)
if not exist "%PY%" (
    echo [ERRO] Python da venv nao encontrado em: %PY%
    echo        Rode o setup do backend antes de usar este launcher.
    pause & exit /b 1
)
if not exist "%FRONTEND%\package.json" (
    echo [ERRO] package.json nao encontrado em: %FRONTEND%
    pause & exit /b 1
)
if not exist "%FRONTEND%\node_modules" (
    echo [INFO] node_modules nao encontrado. Instalando dependencias do frontend...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        popd
        echo [ERRO] npm install falhou.
        pause & exit /b 1
    )
    popd
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
echo [OK] Estrutura local validada.

echo.
echo [2/5] Conferindo dependencias Python essenciais...
"%PY%" -c "import fastapi, sqlalchemy, alembic, yaml, jinja2" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando dependencias Python do backend...
    "%PIP%" install -q -r "%BACKEND%\requirements-dev.txt"
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias Python.
        pause & exit /b 1
    )
) else (
    echo [OK] Dependencias Python encontradas.
)

echo.
echo [3/5] Verificando se o dashboard ja esta no ar...
call :heal_zombie_port 4000 "%FRONTEND_URL%" "frontend"
call :heal_zombie_port 8001 "%BACKEND_URL%/health" "backend"
call :wait_http "%FRONTEND_URL%" 5 "frontend"
if not errorlevel 1 (
    echo [OK] Frontend ja responde em %FRONTEND_URL%
    goto open_dashboard
)

echo.
echo [4/5] Tentando iniciar stack Docker oficial...
call :docker_ready
if errorlevel 1 (
    echo [AVISO] Docker Desktop nao esta pronto.
    if "%FORCE_DOCKER%"=="1" (
        call :try_start_docker
    ) else (
        echo [INFO] Usando modo local. Para forcar Docker, execute: Smart_Juno.bat docker
        goto local_mode
    )
)

call :docker_ready
if not errorlevel 1 (
    echo [INFO] Docker disponivel. Subindo docker-compose.prod.yml...
    if not exist "%COMPOSE_FILE%" (
        echo [ERRO] Compose oficial nao encontrado: %COMPOSE_FILE%
        pause & exit /b 1
    )
    if not exist "%ENV_PROD%" (
        echo [ERRO] .env.prod nao encontrado: %ENV_PROD%
        pause & exit /b 1
    )
    pushd "%ROOT%"
    docker compose --env-file "%ENV_PROD%" -f "%COMPOSE_FILE%" up -d --build
    if errorlevel 1 (
        popd
        echo [AVISO] Docker Compose falhou. Vou tentar modo local.
        goto local_mode
    )
    popd

    call :wait_http "%BACKEND_URL%/health" 90 "backend Docker"
    if errorlevel 1 (
        echo [AVISO] Backend Docker nao respondeu em %BACKEND_URL%/health.
        echo         Verifique: docker compose --env-file "%ENV_PROD%" -f "%COMPOSE_FILE%" logs juno-backend
        goto local_mode
    )

    call :wait_http "%FRONTEND_URL%" 90 "frontend Docker"
    if errorlevel 1 (
        echo [AVISO] Frontend Docker nao respondeu em %FRONTEND_URL%.
        echo         Verifique: docker compose --env-file "%ENV_PROD%" -f "%COMPOSE_FILE%" logs juno-frontend
        goto local_mode
    )

    echo [OK] Stack Docker oficial esta no ar.
    goto open_dashboard
)

:local_mode
echo.
echo [5/5] Iniciando modo local sem Docker...
echo [INFO] Backend local: %BACKEND_URL%
echo [INFO] Frontend local: %FRONTEND_URL%

REM Reforco: um container Docker publicando 8001/4000 RESPONDE HTTP e engana o
REM heal_zombie_port (que so' mata se o HTTP falha), mascarando o modo local com
REM um frontend que aponta para outro backend. Paramos esses containers antes.
call :stop_docker_on_port 8001
call :stop_docker_on_port 4000

call :heal_zombie_port 8001 "%BACKEND_URL%/health" "backend"
call :wait_http "%BACKEND_URL%/health" 5 "backend local existente"
if errorlevel 1 (
    echo [INFO] Aplicando migrations em SQLite local...
    pushd "%BACKEND%"
    set "PYTHONPATH=."
    set "JUNO_ENV=development"
    set "DATABASE_URL=%LOCAL_DB%"
    set "SECRET_KEY=%LOCAL_SECRET_KEY%"
    set "ENCRYPTION_KEY=%LOCAL_ENCRYPTION_KEY%"
    set "ALLOWED_ORIGINS=http://localhost:4000,http://127.0.0.1:4000"
    "%PY%" -m alembic upgrade head
    if errorlevel 1 (
        popd
        echo [ERRO] Alembic falhou no modo local.
        pause & exit /b 1
    )
    popd

    echo [INFO] Log backend: %BACKEND_LOG%
    call :free_port 8001
    start "JUNO Backend :8001" /D "%BACKEND%" cmd /k "set ""PYTHONPATH=."" && set ""JUNO_ENV=development"" && set ""JUNO_DEV_COMPANY_ID=4"" && set ""JUNO_AI_MODEL=%JUNO_AI_MODEL%"" && set ""DATABASE_URL=%LOCAL_DB%"" && set ""SECRET_KEY=%LOCAL_SECRET_KEY%"" && set ""ENCRYPTION_KEY=%LOCAL_ENCRYPTION_KEY%"" && set ""ALLOWED_ORIGINS=http://localhost:4000,http://127.0.0.1:4000"" && call ""%PY%"" -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload > ""%BACKEND_LOG%"" 2>&1"
    call :wait_http "%BACKEND_URL%/health" 90 "backend local"
    if errorlevel 1 (
        echo [ERRO] Backend local nao respondeu em %BACKEND_URL%/health.
        pause & exit /b 1
    )
) else (
    echo [OK] Backend local ja responde.
)

call :heal_zombie_port 4000 "%FRONTEND_URL%" "frontend"
call :wait_http "%FRONTEND_URL%" 5 "frontend local existente"
if errorlevel 1 (
    echo [INFO] Log frontend: %FRONTEND_LOG%
    call :free_port 4000
    start "JUNO Frontend :4000" /D "%FRONTEND%" cmd /k "set ""NEXT_PUBLIC_API_URL=%BACKEND_URL%"" && set ""NEXT_PUBLIC_DEV_COMPANY_ID=4"" && set ""NEXTAUTH_URL=%FRONTEND_URL%"" && call npm run dev > ""%FRONTEND_LOG%"" 2>&1"
    call :wait_http "%FRONTEND_URL%" 120 "frontend local"
    if errorlevel 1 (
        echo [ERRO] Frontend local nao respondeu em %FRONTEND_URL%.
        pause & exit /b 1
    )
) else (
    echo [OK] Frontend local ja responde.
)

:open_dashboard
echo.
echo ============================================================
echo  Servicos JUNO
echo  Dashboard: %DASHBOARD_URL%
echo  Backend  : %BACKEND_URL%/health
echo  API docs : %BACKEND_URL%/docs somente em modo local/dev
echo ============================================================
echo.
call :open_browser "%DASHBOARD_URL%"
echo Dashboard aberto no navegador.
echo Pode fechar esta janela; as janelas Backend/Frontend ficam abertas se o modo local foi usado.
pause
exit /b 0

:verify_mode
echo.
echo ============================================================
echo  JUNO - Verificar e abrir dashboard
echo ============================================================
echo.
if not exist "%PY%" (
    echo [ERRO] Python da venv nao encontrado em: %PY%
    pause & exit /b 1
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
echo [INFO] Conferindo portas 4000/8001 (mata processo zombie se HTTP falhar)...
call :heal_zombie_port 4000 "%FRONTEND_URL%" "frontend"
call :heal_zombie_port 8001 "%BACKEND_URL%/health" "backend"
call :wait_http "%FRONTEND_URL%" 8 "frontend"
if not errorlevel 1 (
    echo [OK] Dashboard respondendo.
    goto open_dashboard
)
echo [AVISO] Dashboard nao respondeu. Vou subir o modo local...
goto local_mode

:kill_all
echo.
echo [LIMPEZA] Encerrando instancias JUNO anteriores (backend/frontend)...
REM 1) Por porta: 8001 (backend) e 4000 (frontend) -- taskkill /F (com elevacao
REM    derruba ate processos protegidos que resistiram ao Stop-Process).
for %%P in (8001 4000) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%P " ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1 && echo   [OK] porta %%P liberada ^(PID %%a^)
    )
)
REM 2) Backends uvicorn orfaos do JUNO (python rodando app.main:app, sem porta ativa).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'app.main:app' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; Write-Host ('   [OK] backend orfao encerrado (PID ' + $_.ProcessId + ')') } catch {} }"
REM 3) Frontend next dev orfaos do JUNO (node em janus\frontend).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'janus' -and $_.CommandLine -match 'frontend' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; Write-Host ('   [OK] frontend orfao encerrado (PID ' + $_.ProcessId + ')') } catch {} }"
ping -n 3 127.0.0.1 >nul
echo [LIMPEZA] Concluida. Iniciando do zero.
echo.
exit /b 0

:clear_next
echo [RESET] Limpando cache do Turbopack (.next) para rebuild limpo do frontend...
if exist "%FRONTEND%\.next" (
    rmdir /s /q "%FRONTEND%\.next" >nul 2>&1
    if exist "%FRONTEND%\.next" (
        echo [AVISO] Nao consegui remover todo o .next ^(arquivo em uso?^). Feche o frontend e tente de novo.
    ) else (
        echo [OK] .next removido. O proximo start recompila do zero.
    )
)
exit /b 0

:free_ports
call :free_port 8001
call :free_port 4000
exit /b 0

:free_port
powershell -NoProfile -Command "$port=%~1; $procs = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($procs) { Write-Host ('[INFO] Liberando porta ' + $port + '...'); foreach ($procId in $procs) { try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host ('[OK] PID ' + $procId + ' encerrado.') } catch {} } }"
exit /b 0

:stop_docker_on_port
REM %1 = porta host. Para containers Docker JUNO que publicam essa porta, para
REM que o modo local possa bindar (evita o frontend Docker mascarar o local).
docker info >nul 2>&1
if errorlevel 1 exit /b 0
for /f "delims=" %%c in ('docker ps --filter "publish=%~1" --format "{{.Names}}" 2^>nul') do (
    echo %%c | findstr /i "juno" >nul && (
        echo [INFO] Parando container Docker '%%c' que ocupa a porta %~1 ^(conflito com modo local^)...
        docker update --restart=no %%c >nul 2>&1
        docker stop %%c >nul 2>&1
    )
)
exit /b 0

:heal_zombie_port
powershell -NoProfile -Command "$port=%~1; $url='%~2'; $name='%~3'; $listening = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue); if (-not $listening) { exit 0 }; $ok = $false; try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 4; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { $ok = $true } } catch {}; if ($ok) { exit 0 }; Write-Host ('[AVISO] Porta ' + $port + ' ocupada mas ' + $name + ' nao responde HTTP - reiniciando...'); $procs = $listening | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($procId in $procs) { try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host ('[OK] PID ' + $procId + ' encerrado.') } catch {} }; Start-Sleep -Seconds 2"
exit /b 0

:open_browser
start "" "%~1"
rundll32 url.dll,FileProtocolHandler "%~1"
exit /b 0

:docker_ready
docker info >nul 2>&1
exit /b %errorlevel%

:try_start_docker
set "DOCKER_EXE="
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if "%DOCKER_EXE%"=="" if exist "%LocalAppData%\Docker\Docker Desktop.exe" set "DOCKER_EXE=%LocalAppData%\Docker\Docker Desktop.exe"

if "%DOCKER_EXE%"=="" (
    echo [AVISO] Docker Desktop nao encontrado. Usando modo local.
    exit /b 1
)

echo [INFO] Abrindo Docker Desktop. Isso pode levar ate 2 minutos...
start "" "%DOCKER_EXE%"
for /l %%i in (1,1,120) do (
    docker info >nul 2>&1
    if not errorlevel 1 exit /b 0
    timeout /t 1 /nobreak >nul
)
echo [AVISO] Docker Desktop nao ficou pronto no tempo limite.
exit /b 1

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
if "!WAIT_TRY!"=="1" echo [INFO] Aguardando %WAIT_NAME% em %WAIT_URL%...
powershell -NoProfile -Command "Start-Sleep -Seconds 1"
goto wait_http_loop
