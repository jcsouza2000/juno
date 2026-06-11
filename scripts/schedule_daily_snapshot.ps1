# Agenda o job de snapshot diario no Task Scheduler (Windows)
# Uso (Admin): powershell -ExecutionPolicy Bypass -File scripts\schedule_daily_snapshot.ps1

$TaskName = "JUNO-Daily-Snapshot"
$Root = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Root "janus\backend\.venv\Scripts\python.exe"
$Job = Join-Path $Root "scripts\daily_snapshot_job.py"
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "daily-snapshot.log"

$Wrapper = Join-Path $Root "scripts\run_daily_snapshot.bat"
$Action = New-ScheduledTaskAction -Execute $Wrapper -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "JUNO Fase A: snapshot diario de KPIs/demonstracoes por tenant" | Out-Null

Write-Host "Tarefa agendada: $TaskName"
Write-Host "Horario: diario as 02:00"
Write-Host "Comando: $Python $Job"
Write-Host "Log sugerido: $LogFile"
