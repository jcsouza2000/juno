<#
.SYNOPSIS
    JUNO Database Restore — Restaura backup do PostgreSQL

.DESCRIPTION
    Restaura um backup .sql ou .zip para o banco juno_db.
    ATENÇÃO: Isso SUBSTITUI todos os dados atuais!

.PARAMETER BackupFile
    Caminho do arquivo de backup (.sql ou .zip)

.EXAMPLE
    .\restore_database.ps1 -BackupFile "..\backups\juno_backup_20260511_120000.zip"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [string]$ContainerName = "juno-postgres",
    [string]$DbName = "juno_db",
    [string]$DbUser = "juno"
)

$ErrorActionPreference = "Stop"

Write-Host "RESTAURACAO DE BANCO" -ForegroundColor Red
Write-Host "   Isso APAGARÁ todos os dados atuais!" -ForegroundColor Red
Write-Host "   Backup: $BackupFile" -ForegroundColor Yellow

$confirm = Read-Host "`nDigite 'RESTAURAR' para confirmar"
if ($confirm -ne "RESTAURAR") {
    Write-Host "Operação cancelada." -ForegroundColor Yellow
    exit 0
}

try {
    # Extrair se for zip
    $sqlFile = $BackupFile
    if ($BackupFile -match '\.zip$') {
        $extractDir = [System.IO.Path]::GetTempPath()
        Expand-Archive -Path $BackupFile -DestinationPath $extractDir -Force
        $sqlFile = Join-Path $extractDir ([System.IO.Path]::GetFileNameWithoutExtension($BackupFile) + ".sql")
        Write-Host "Backup extraido para: $sqlFile" -ForegroundColor Green
    }

    # Dropar e recriar banco
    Write-Host "Dropando banco atual..." -ForegroundColor Yellow
    docker exec $ContainerName dropdb -U $DbUser --if-exists $DbName
    docker exec $ContainerName createdb -U $DbUser $DbName

    # Restaurar
    Write-Host "Restaurando backup..." -ForegroundColor Cyan
    Get-Content $sqlFile | docker exec -i $ContainerName psql -U $DbUser -d $DbName

    Write-Host "`nRestauracao concluida!" -ForegroundColor Green
    Write-Host "   Banco $DbName restaurado com sucesso." -ForegroundColor Green

    # Limpar arquivo extraído
    if ($BackupFile -match '\.zip$') {
        Remove-Item $sqlFile -Force
    }

} catch {
    Write-Host "Erro na restauracao: $_" -ForegroundColor Red
    exit 1
}
