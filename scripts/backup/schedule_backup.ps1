<#
.SYNOPSIS
    Agenda backup automático do JUNO no Windows Task Scheduler

.DESCRIPTION
    Cria uma tarefa agendada para executar backup diário do banco.
    Requer privilégios de administrador.

.PARAMETER Time
    Horário do backup (formato HH:MM, padrão: 02:00)

.PARAMETER Frequency
    Frequência: Daily, Hourly (padrão: Daily)

.EXAMPLE
    .\schedule_backup.ps1 -Time "02:00" -Frequency Daily
#>

param(
    [string]$Time = "02:00",
    [ValidateSet("Daily", "Hourly")]
    [string]$Frequency = "Daily"
)

$ErrorActionPreference = "Stop"

$TaskName = "JUNO_Database_Backup"
$ScriptPath = Resolve-Path "$PSScriptRoot\backup_database.ps1"
$LogPath = "$PSScriptRoot\..\logs\backup.log"

# Criar diretório de logs
$logDir = Split-Path $LogPath -Parent
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Verificar se está como admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (!$isAdmin) {
    Write-Error "Este script precisa ser executado como Administrador!"
    exit 1
}

# Remover tarefa existente
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "🗑️  Tarefa anterior removida." -ForegroundColor Yellow
}

# Criar ação
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$ScriptPath`" >> `"$LogPath`" 2>&1"

# Criar trigger
if ($Frequency -eq "Daily") {
    $Trigger = New-ScheduledTaskTrigger -Daily -At $Time
} else {
    $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 365)
}

# Criar configurações
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Registrar tarefa
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Backup automático do banco JUNO" | Out-Null

Write-Host "✅ Tarefa agendada criada!" -ForegroundColor Green
Write-Host "   Nome: $TaskName" -ForegroundColor White
Write-Host "   Frequência: $Frequency" -ForegroundColor White
Write-Host "   Horário: $Time" -ForegroundColor White
Write-Host "   Script: $ScriptPath" -ForegroundColor White
Write-Host "   Logs: $LogPath" -ForegroundColor White
Write-Host "`nPara verificar: Get-ScheduledTask -TaskName $TaskName" -ForegroundColor Cyan
Write-Host "Para executar agora: Start-ScheduledTask -TaskName $TaskName" -ForegroundColor Cyan
