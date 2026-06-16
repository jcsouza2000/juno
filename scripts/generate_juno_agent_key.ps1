# Gera par de chaves Ed25519 para juno_audit (README)
param(
    [switch]$SetRailwaySecret
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$AuditRoot = Join-Path $Root "juno_audit"

$py = Join-Path $Root "janus\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "py" ; $pyArgs = @("-3.11") } else { $pyArgs = @() }

$code = @"
import sys
sys.path.insert(0, r'$AuditRoot')
from juno_audit.signer import generate_keypair
sk, pk = generate_keypair()
print('JUNO_AGENT_SK=' + sk)
print('JUNO_AGENT_PK=' + pk)
print('')
print('PRIVADA (cofre / Railway secret JUNO_AGENT_SK):')
print(sk)
print('PUBLICA (registry / pubkeys.json):')
print(pk)
"@

$output = & $py @pyArgs -c $code 2>&1
$output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($SetRailwaySecret) {
    $skLine = $output | Where-Object { $_ -match '^JUNO_AGENT_SK=' } | Select-Object -First 1
    if (-not $skLine) {
        Write-Host "[FAIL] Nao foi possivel extrair chave privada"
        exit 1
    }
    $sk = $skLine -replace '^JUNO_AGENT_SK=', ''
    railway variables set "JUNO_AGENT_SK=$sk" --secret
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "[OK] Railway secret JUNO_AGENT_SK definido"
}
