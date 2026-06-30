@echo off
setlocal EnableExtensions
title JUNO - Reset Limpo (mata fantasmas e limpa cache)

echo ============================================================
echo  JUNO - RESET LIMPO
echo  Mata processos fantasmas nas portas 4000 e 8001,
echo  remove o cache .next e prepara para subir limpo.
echo ============================================================
echo.

echo [1/4] Encerrando TODOS os processos node...
taskkill /F /IM node.exe >nul 2>&1
echo [OK] node encerrado.

echo.
echo [2/4] Liberando portas 4000 e 8001 (matando o PID dono)...
for %%P in (4000 8001) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        echo     - Porta %%P ocupada pelo PID %%A. Encerrando...
        taskkill /F /PID %%A >nul 2>&1
    )
)
echo [OK] Portas liberadas.

echo.
echo [3/4] Removendo cache .next do frontend (forca rebuild limpo)...
set "NEXTDIR=%~dp0janus\frontend\.next"
if exist "%NEXTDIR%" (
    rmdir /S /Q "%NEXTDIR%" >nul 2>&1
    echo [OK] .next removido.
) else (
    echo [OK] .next ja estava limpo.
)

echo.
echo [4/4] Conferindo se as portas ficaram livres...
netstat -ano | findstr ":4000 :8001" | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    echo [OK] Portas 4000 e 8001 LIVRES.
) else (
    echo [AVISO] Ainda ha algo nas portas. Veja abaixo:
    netstat -ano | findstr ":4000 :8001" | findstr LISTENING
)

echo.
echo ============================================================
echo  Limpeza concluida. Agora suba o JUNO local com:
echo.
echo      Smart_Juno.bat local
echo.
echo  Depois abra uma janela ANONIMA nova em:
echo      http://127.0.0.1:4000/integrations
echo ============================================================
echo.
pause
