# Aguarda backend prod e executa bootstrap (seed + admin)
param(
    [string]$Base = "http://127.0.0.1:8002",
    [string]$Container = "juno-prod-local-juno-backend-1"
)

$ErrorActionPreference = "Stop"

Write-Host "Aguardando $Base ..."
for ($i = 0; $i -lt 40; $i++) {
    try {
        $r = Invoke-RestMethod "$Base/api/v1/health/ready" -TimeoutSec 5
        if ($r.ready) { break }
    } catch {}
    Start-Sleep -Seconds 5
    if ($i -eq 39) {
        Write-Host "[FAIL] Backend nao ficou ready"
        docker logs $Container --tail 40
        exit 1
    }
}

Write-Host "Executando bootstrap no container..."
docker exec $Container python -m app.bootstrap_prod_local
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[OK] Admin: admin@juno.local / Admin123! (company_id=1)"
