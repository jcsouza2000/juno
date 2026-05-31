# ====================================================================
# JUNO — Script de limpeza pós-auditoria 2026-05
# ====================================================================
# Este script remove artefatos legados que sobraram da fase de
# experimentação (backups, dumps de árvore, bancos SQLite antigos,
# scripts setup_fase*.ps1 que já foram consolidados no CHANGELOG).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\cleanup_legacy.ps1
#
# REVISE antes de rodar. Cada bloco está com Write-Host comentando
# o que será apagado. Comente os blocos que você quer preservar.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== JUNO cleanup: $root ===" -ForegroundColor Cyan

# --- 1) Venvs no raiz (deveriam estar em janus/backend/.venv) -----------
Write-Host "`n[1/7] Venvs duplicados no raiz..." -ForegroundColor Yellow
Get-ChildItem -Path $root -Directory -Filter ".venv*" | ForEach-Object {
    Write-Host "  Removendo $($_.FullName)"
    Remove-Item -Recurse -Force $_.FullName
}

# --- 2) Dumps de árvore antigos (_01_*.txt etc) -------------------------
Write-Host "`n[2/7] Dumps de árvore / análises antigas..." -ForegroundColor Yellow
Get-ChildItem -Path $root -File | Where-Object {
    $_.Name -match '^_(0\d|1\d)_.*\.txt$'
} | ForEach-Object {
    Write-Host "  Removendo $($_.Name)"
    Remove-Item -Force $_.FullName
}

# --- 3) Checkpoints de fase ---------------------------------------------
Write-Host "`n[3/7] Checkpoints de fase..." -ForegroundColor Yellow
Get-ChildItem -Path $root -File -Filter ".fase*_checkpoint.json" | ForEach-Object {
    Write-Host "  Removendo $($_.Name)"
    Remove-Item -Force $_.FullName
}

# --- 4) Backups *.backup.fase* ------------------------------------------
Write-Host "`n[4/7] Backups *.backup.fase*..." -ForegroundColor Yellow
Get-ChildItem -Path $root -Recurse -File -Filter "*.backup.fase*" | ForEach-Object {
    Write-Host "  Removendo $($_.FullName.Replace($root,''))"
    Remove-Item -Force $_.FullName
}

# --- 5) Bancos SQLite antigos -------------------------------------------
Write-Host "`n[5/7] Bancos SQLite antigos..." -ForegroundColor Yellow
@(
    "janus\backend\janus.db",
    "janus\backend\juno.db",
    "janus\backend\juno_migrated.db",
    "janus\backend\alembic_bootstrap.db"
) | ForEach-Object {
    $path = Join-Path $root $_
    if (Test-Path $path) {
        Write-Host "  Removendo $_"
        Remove-Item -Force $path
    }
}

# --- 6) Setup scripts antigos por fase ----------------------------------
# Mantém: setup_juno_fases1_5_13_completo.ps1 (consolidado)
# Remove: setup_fase{1..13}_*.ps1 individuais
Write-Host "`n[6/7] Setup scripts antigos..." -ForegroundColor Yellow
Get-ChildItem -Path $root -File | Where-Object {
    $_.Name -match '^setup_fase\d+_.*\.ps1$'
} | ForEach-Object {
    Write-Host "  Removendo $($_.Name)"
    Remove-Item -Force $_.FullName
}

# --- 7) Scripts one-off na raiz -----------------------------------------
Write-Host "`n[7/7] Scripts one-off no raiz..." -ForegroundColor Yellow
@(
    "analise_janus_ai.ps1",
    "check_line772.py",
    "check_line799.py",
    "check_quotes.py",
    "fix_fase13.py",
    "fase5_output.txt",
    "fase6_output.txt",
    "fase7_output.txt",
    "Setup_Fase2_completo.ps1"
) | ForEach-Object {
    $path = Join-Path $root $_
    if (Test-Path $path) {
        Write-Host "  Removendo $_"
        Remove-Item -Force $path
    }
}

Write-Host "`n=== Limpeza concluída ===" -ForegroundColor Green
Write-Host "Tamanho atual do projeto:" -ForegroundColor Cyan
Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
    Measure-Object -Property Length -Sum |
    ForEach-Object {
        $mb = [math]::Round($_.Sum / 1MB, 2)
        Write-Host "  $($_.Count) arquivos, $mb MB"
    }
