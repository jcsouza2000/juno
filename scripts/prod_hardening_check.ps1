# Valida .env de producao antes do deploy (somente leitura)
param(
    [string]$EnvFile = (Join-Path (Split-Path $PSScriptRoot -Parent) ".env.prod")
)

$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

if (-not (Test-Path $EnvFile)) {
    Write-Host "[FAIL] Arquivo nao encontrado: $EnvFile"
    Write-Host "Copie .env.prod.example para .env.prod e preencha os valores."
    exit 1
}

$vars = @{}
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { return }
    $key = $line.Substring(0, $idx).Trim()
    $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
    $vars[$key] = $val
}

function Require-Key($key) {
    if (-not $vars.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($vars[$key])) {
        $errors.Add("Variavel obrigatoria ausente ou vazia: $key")
    }
}

Require-Key 'JUNO_ENV'
Require-Key 'JUNO_DEV_AUTH_BYPASS'
Require-Key 'DATABASE_URL'
Require-Key 'SECRET_KEY'
Require-Key 'ENCRYPTION_KEY'
Require-Key 'ALLOWED_ORIGINS'

if ($vars['JUNO_ENV'] -and $vars['JUNO_ENV'].ToLower() -ne 'production') {
    $warnings.Add("JUNO_ENV=$($vars['JUNO_ENV']) - esperado 'production' para hardening final")
}

if ($vars['JUNO_DEV_AUTH_BYPASS'] -match '^(true|1|yes)$') {
    $errors.Add('JUNO_DEV_AUTH_BYPASS deve ser false em producao')
}

if ($vars['DATABASE_URL'] -match '^sqlite:') {
    $errors.Add('DATABASE_URL nao pode ser SQLite em producao')
}

if ($vars['SECRET_KEY'] -and $vars['SECRET_KEY'].Length -lt 32) {
    $errors.Add('SECRET_KEY precisa ter pelo menos 32 caracteres')
}

if ($vars['ALLOWED_ORIGINS'] -match 'localhost|127\.0\.0\.1') {
    $warnings.Add('ALLOWED_ORIGINS contem localhost - revise antes de go-live publico')
}

if ($vars['POSTGRES_PASSWORD'] -match 'troque_esta_senha|changeme|password') {
    $msg = 'POSTGRES_PASSWORD ainda usa valor de exemplo'
    if ($EnvFile -match '\.example$') {
        $warnings.Add("$msg (ok em arquivo .example)")
    } else {
        $errors.Add($msg)
    }
}

Write-Host "=== JUNO Prod Hardening Check ==="
Write-Host "Arquivo: $EnvFile"
Write-Host ''

foreach ($w in $warnings) { Write-Host "[WARN] $w" -ForegroundColor Yellow }
foreach ($e in $errors) { Write-Host "[FAIL] $e" -ForegroundColor Red }

if ($errors.Count -eq 0 -and $warnings.Count -eq 0) {
    Write-Host '[OK] Ambiente passou na validacao basica de hardening.' -ForegroundColor Green
    exit 0
}
if ($errors.Count -eq 0) {
    Write-Host "[OK] Sem erros bloqueantes ($($warnings.Count) aviso(s))." -ForegroundColor Green
    exit 0
}
Write-Host ''
Write-Host "Corrija $($errors.Count) erro(s) antes do deploy."
exit 1
