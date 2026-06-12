# Sobe stack Docker prod local usando SOMENTE .env.prod (evita vars do shell).
param(
    [string]$EnvFile = (Join-Path (Split-Path $PSScriptRoot -Parent) ".env.prod")
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

if (-not (Test-Path $EnvFile)) {
    Write-Host "[FAIL] $EnvFile nao encontrado. Rode: python scripts/generate_env_prod.py"
    exit 1
}

# Carrega .env.prod no processo (substituicao do compose)
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { return }
    $key = $line.Substring(0, $idx).Trim()
    $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
    Set-Item -Path "Env:$key" -Value $val
}

Write-Host "=== JUNO Docker prod local ==="
Write-Host "Backend: http://localhost:8002"
Write-Host "Frontend: http://localhost:4002"
Write-Host ""

powershell -NoProfile -File (Join-Path $PSScriptRoot "prod_hardening_check.ps1") -EnvFile $EnvFile
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Push-Location $Root
try {
    docker compose `
        -f docker-compose.prod.yml `
        -f docker-compose.prod.local.yml `
        --env-file $EnvFile `
        -p juno-prod-local `
        up -d --build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ''
    Write-Host 'Aguardando backend e bootstrap admin...'
    powershell -NoProfile -File (Join-Path $PSScriptRoot 'bootstrap_prod_docker.ps1')
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
