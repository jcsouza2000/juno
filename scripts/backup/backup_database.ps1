<#
.SYNOPSIS
    JUNO Database Backup — Backup automático do PostgreSQL
    Pode ser agendado via Windows Task Scheduler

.DESCRIPTION
    Cria backup do banco juno_db em arquivo .sql com timestamp.
    Mantém apenas os últimos N backups (padrão: 30 dias).

.PARAMETER RetentionDays
    Número de dias para manter backups (padrão: 30)

.PARAMETER BackupDir
    Diretório de destino dos backups (padrão: ./backups)

.EXAMPLE
    .\backup_database.ps1
    .\backup_database.ps1 -RetentionDays 7 -BackupDir "D:\JUNO\Backups"
#>

param(
    [int]$RetentionDays = 30,
    [string]$BackupDir = "$PSScriptRoot\..\backups",
    [string]$ContainerName = "juno-postgres",
    [string]$DbName = "juno_db",
    [string]$DbUser = "juno"
)

$ErrorActionPreference = "Stop"

$DbPass = $env:POSTGRES_PASSWORD

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = "juno_backup_$Timestamp.sql"
$BackupPath = Join-Path $BackupDir $BackupFile
$CompressedFile = "juno_backup_$Timestamp.zip"

# Criar diretório se não existir
if (!(Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    Write-Host "Diretorio de backup criado: $BackupDir" -ForegroundColor Green
}

Write-Host "Iniciando backup do banco $DbName..." -ForegroundColor Cyan
Write-Host "   Destino: $BackupPath" -ForegroundColor Gray
if ([string]::IsNullOrWhiteSpace($DbPass)) {
    throw "Defina POSTGRES_PASSWORD antes de executar o backup."
}
$env:PGPASSWORD = $DbPass

try {
    # Verificar se container está rodando
    $containerRunning = docker ps --format "{{.Names}}" | Select-String $ContainerName
    if (!$containerRunning) {
        throw "Container $ContainerName não está rodando!"
    }

    # Executar pg_dump dentro do container
    docker exec -e PGPASSWORD=$DbPass $ContainerName pg_dump -U $DbUser -d $DbName --no-owner --no-privileges > $BackupPath

    if (Test-Path $BackupPath) {
        $size = (Get-Item $BackupPath).Length / 1MB
        Write-Host "Backup concluido!" -ForegroundColor Green
        Write-Host "   Arquivo: $BackupFile" -ForegroundColor Green
        Write-Host "   Tamanho: $([math]::Round($size, 2)) MB" -ForegroundColor Green

        # Comprimir backup
        Compress-Archive -Path $BackupPath -DestinationPath (Join-Path $BackupDir $CompressedFile) -Force
        Remove-Item $BackupPath
        $zipSize = (Get-Item (Join-Path $BackupDir $CompressedFile)).Length / 1MB
        Write-Host "   Compactado: $CompressedFile ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Green

        # Limpar backups antigos
        $cutoffDate = (Get-Date).AddDays(-$RetentionDays)
        $oldBackups = Get-ChildItem $BackupDir -Filter "juno_backup_*.zip" | Where-Object {
            $_.CreationTime -lt $cutoffDate
        }

        foreach ($old in $oldBackups) {
            Remove-Item $old.FullName -Force
            Write-Host "Removido backup antigo: $($old.Name)" -ForegroundColor Yellow
        }

        # Relatório
        $totalBackups = (Get-ChildItem $BackupDir -Filter "juno_backup_*.zip").Count
        Write-Host "`nResumo:" -ForegroundColor Cyan
        Write-Host "   Backups mantidos: $totalBackups" -ForegroundColor White
        Write-Host "   Retenção: $RetentionDays dias" -ForegroundColor White
        Write-Host "   Diretório: $BackupDir" -ForegroundColor White

    } else {
        throw "Arquivo de backup não foi criado!"
    }

} catch {
    Write-Host "Erro no backup: $_" -ForegroundColor Red
    exit 1
}
