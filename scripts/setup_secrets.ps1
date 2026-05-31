# =====================================================================
# JUNO — Setup de secrets locais (SECRET_KEY, ENCRYPTION_KEY)
# =====================================================================
# Gera chaves criptograficamente seguras e grava em janus/backend/.env
# SEM exibir os valores na tela. Idempotente: se o .env já tiver as
# chaves, não sobrescreve (a menos que -Force seja passado).
#
# Uso:
#   .\scripts\setup_secrets.ps1                  # gera se faltarem
#   .\scripts\setup_secrets.ps1 -Force           # regenera tudo
#   .\scripts\setup_secrets.ps1 -SmokeTest       # roda valid + crypto
#   .\scripts\setup_secrets.ps1 -StartServer     # sobe uvicorn no final

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$SmokeTest,
    [switch]$StartServer,
    [int]$Port = 9050
)

$ErrorActionPreference = "Stop"

# --- Resolve paths -------------------------------------------------------
$RepoRoot   = $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "janus\backend"))) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$BackendDir = Join-Path $RepoRoot "janus\backend"
$EnvFile    = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $BackendDir ".env.example"
$VenvDir    = Join-Path $BackendDir ".venv"
$Python     = Join-Path $VenvDir "Scripts\python.exe"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Write-OK($msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "  [X]  $msg" -ForegroundColor Red }

# --- 1) Verifica ambiente ------------------------------------------------
Write-Step "Verificando ambiente"

if (-not (Test-Path $BackendDir)) {
    Write-Err "Diretório do backend não encontrado: $BackendDir"
    exit 1
}
Write-OK "Backend: $BackendDir"

if (-not (Test-Path $Python)) {
    Write-Warn "venv não encontrada em $VenvDir"
    Write-Host "  Criando venv e instalando deps (pode demorar 1-2 min)..." -ForegroundColor Gray
    Push-Location $BackendDir
    try {
        python -m venv .venv
        & $Python -m pip install --quiet --upgrade pip
        & $Python -m pip install --quiet -r requirements.txt
    } finally {
        Pop-Location
    }
    Write-OK "venv criada e deps instaladas"
} else {
    Write-OK "venv: $VenvDir"
}

# --- 2) Garante .env existe (copia do example se necessário) -------------
Write-Step "Verificando .env"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-OK ".env criado a partir de .env.example"
    } else {
        # Cria .env mínimo
        @"
JUNO_ENV=development
SECRET_KEY=
ENCRYPTION_KEY=
DATABASE_URL=
ALLOWED_ORIGINS=http://localhost:4000,http://localhost:9050
LOGIN_RATE_LIMIT=5/minute
LOG_LEVEL=INFO
"@ | Set-Content -Path $EnvFile -Encoding UTF8 -NoNewline
        Write-OK ".env criado do zero"
    }
} else {
    Write-OK ".env já existe"
}

# --- 3) Lê o .env atual --------------------------------------------------
function Read-EnvFile($path) {
    $dict = @{}
    foreach ($line in Get-Content $path -Encoding UTF8) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*$') { continue }
        if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$') {
            $dict[$matches[1]] = $matches[2]
        }
    }
    return $dict
}

function Write-EnvFile($path, $dict) {
    # Reescreve mantendo a ordem das chaves do dicionário
    $lines = @()
    foreach ($key in $dict.Keys) {
        $val = $dict[$key]
        $lines += "$key=$val"
    }
    Set-Content -Path $path -Value $lines -Encoding UTF8
}

$envData = Read-EnvFile $EnvFile

# --- 4) Gera chaves se necessário ---------------------------------------
Write-Step "Gerando/validando chaves"

function Get-NewSecretKey {
    & $Python -c "import secrets; print(secrets.token_urlsafe(64))"
}

function Get-NewFernetKey {
    & $Python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

# SECRET_KEY
$needSecret = $Force -or (-not $envData.ContainsKey("SECRET_KEY")) -or [string]::IsNullOrWhiteSpace($envData["SECRET_KEY"])
if ($needSecret) {
    $envData["SECRET_KEY"] = Get-NewSecretKey
    Write-OK "SECRET_KEY gerada (len: $($envData['SECRET_KEY'].Length))"
} else {
    Write-OK "SECRET_KEY já presente (len: $($envData['SECRET_KEY'].Length))"
}

# ENCRYPTION_KEY
$needEnc = $Force -or (-not $envData.ContainsKey("ENCRYPTION_KEY")) -or [string]::IsNullOrWhiteSpace($envData["ENCRYPTION_KEY"])
if ($needEnc) {
    $envData["ENCRYPTION_KEY"] = Get-NewFernetKey
    Write-OK "ENCRYPTION_KEY gerada (len: $($envData['ENCRYPTION_KEY'].Length))"
} else {
    Write-OK "ENCRYPTION_KEY já presente (len: $($envData['ENCRYPTION_KEY'].Length))"
}

# Garantir defaults sensatos para dev
if (-not $envData.ContainsKey("JUNO_ENV") -or [string]::IsNullOrWhiteSpace($envData["JUNO_ENV"])) {
    $envData["JUNO_ENV"] = "development"
}
if (-not $envData.ContainsKey("ALLOWED_ORIGINS") -or [string]::IsNullOrWhiteSpace($envData["ALLOWED_ORIGINS"])) {
    $envData["ALLOWED_ORIGINS"] = "http://localhost:4000,http://localhost:9050"
} elseif ($envData["ALLOWED_ORIGINS"] -match "http://localhost:3000" -and $envData["ALLOWED_ORIGINS"] -notmatch "http://localhost:4000") {
    # Alinha ambientes legados ao protocolo do SmartJuno.
    $envData["ALLOWED_ORIGINS"] = $envData["ALLOWED_ORIGINS"] -replace "http://localhost:3000", "http://localhost:4000"
}
if (-not $envData.ContainsKey("LOG_LEVEL") -or [string]::IsNullOrWhiteSpace($envData["LOG_LEVEL"])) {
    $envData["LOG_LEVEL"] = "INFO"
}
if (-not $envData.ContainsKey("LOGIN_RATE_LIMIT") -or [string]::IsNullOrWhiteSpace($envData["LOGIN_RATE_LIMIT"])) {
    $envData["LOGIN_RATE_LIMIT"] = "5/minute"
}
# DATABASE_URL fica vazia em dev (cai para sqlite local). Em prod, pessoa preenche.

Write-EnvFile $EnvFile $envData
Write-OK ".env atualizado"

# Permissões: tornar o .env legível só pelo usuário (boa prática Windows)
try {
    $acl = Get-Acl $EnvFile
    $acl.SetAccessRuleProtection($true, $false)  # remove herança
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().Name,
        "FullControl", "Allow"
    )
    $acl.SetAccessRule($rule)
    Set-Acl -Path $EnvFile -AclObject $acl
    Write-OK "Permissões do .env: somente o usuário atual"
} catch {
    Write-Warn "Não foi possível ajustar ACL do .env: $($_.Exception.Message)"
}

# --- 5) Smoke test ------------------------------------------------------
if ($SmokeTest -or $StartServer) {
    Write-Step "Smoke test (validação + crypto roundtrip)"

    Push-Location $BackendDir
    try {
        $env:PYTHONPATH = "."
        $env:JUNO_ENV          = $envData["JUNO_ENV"]
        $env:SECRET_KEY        = $envData["SECRET_KEY"]
        $env:ENCRYPTION_KEY    = $envData["ENCRYPTION_KEY"]
        $env:DATABASE_URL      = $envData["DATABASE_URL"]
        $env:ALLOWED_ORIGINS   = $envData["ALLOWED_ORIGINS"]
        $env:LOG_LEVEL         = "WARNING"

        $script = @"
from app.config import settings
from app.core.crypto import encrypt, decrypt

print(f'JUNO_ENV: {settings.JUNO_ENV}')
print(f'SECRET_KEY length: {len(settings.SECRET_KEY)} (esperado >= 32)')
print(f'ENCRYPTION_KEY length: {len(settings.ENCRYPTION_KEY)} (esperado = 44)')
print(f'DATABASE_URL configurada: {bool(settings.DATABASE_URL)}')
print(f'CORS origins: {settings.cors_origins}')

# Crypto roundtrip
sample = 'senha-de-erp-de-teste'
ct = encrypt(sample)
pt = decrypt(ct)
assert pt == sample, f'Roundtrip falhou: {sample!r} -> {pt!r}'
print('Crypto Fernet roundtrip: OK')

# Smoke import dos routers
from app.main import app
paths = sorted({r.path for r in app.routes})
print(f'Rotas registradas: {len(paths)}')
"@
        & $Python -c $script
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Smoke test falhou (ver erro acima)"
            exit 1
        }
        Write-OK "Smoke test passou"
    } finally {
        Pop-Location
    }
}

# --- 6) Pytest (opcional) -----------------------------------------------
if ($SmokeTest) {
    Write-Step "Rodando pytest"
    Push-Location $BackendDir
    try {
        $env:PYTHONPATH = "."
        & $Python -m pytest --no-cov -q 2>&1 | Select-Object -Last 15
    } finally {
        Pop-Location
    }
}

# --- 7) Subir uvicorn (opcional) ----------------------------------------
if ($StartServer) {
    Write-Step "Subindo uvicorn na porta $Port"
    Write-Host "  Acesse: http://localhost:$Port" -ForegroundColor Gray
    Write-Host "  Docs:   http://localhost:$Port/docs" -ForegroundColor Gray
    Write-Host "  Health: http://localhost:$Port/health" -ForegroundColor Gray
    Write-Host "  (Ctrl+C para parar)" -ForegroundColor Gray
    Push-Location $BackendDir
    try {
        $env:PYTHONPATH = "."
        & $Python -m uvicorn app.main:app --reload --port $Port
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Setup concluido." -ForegroundColor Green
Write-Host "O .env esta em: $EnvFile" -ForegroundColor Gray
Write-Host "Proximas vezes: .\scripts\setup_secrets.ps1 -SmokeTest -StartServer" -ForegroundColor Gray
