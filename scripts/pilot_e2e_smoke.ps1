# Fase A - smoke E2E automatizado (API) do piloto JUNO
param(
    [string]$Base = "http://127.0.0.1:8001",
    [int]$CompanyId = 4
)

$results = New-Object System.Collections.Generic.List[object]

function Add-Result($name, $ok, $detail) {
    $results.Add([pscustomobject]@{ Step = $name; Status = $(if ($ok) { 'OK' } else { 'FAIL' }); Detail = $detail })
}

function Try-Step($name, [scriptblock]$Block) {
    try {
        & $Block
        Add-Result $name $true ''
        Write-Host "[OK] $name"
    } catch {
        Add-Result $name $false $_.Exception.Message
        Write-Host "[FAIL] $name - $($_.Exception.Message)"
    }
}

Try-Step 'health/ready' {
    $r = Invoke-RestMethod "$Base/api/v1/health/ready" -TimeoutSec 10
    if (-not $r.ready) { throw 'ready=false' }
}

Try-Step 'ollama health' {
    $r = Invoke-RestMethod "$Base/ai/ollama/health" -TimeoutSec 10
    if (-not $r.online) { throw 'ollama offline' }
}

Try-Step 'kpis unified' {
    $r = Invoke-RestMethod "$Base/kpis/$CompanyId/unified" -TimeoutSec 120
    if (-not $r) { throw 'empty payload' }
}

Try-Step 'valuation scenario' {
    $r = Invoke-RestMethod "$Base/financials/$CompanyId/valuation/scenario?anos=5" -TimeoutSec 30
    if ($r.valuation.enterprise_value -le 0) { throw 'EV invalido' }
}

Try-Step 'data inventory' {
    $r = Invoke-RestMethod "$Base/data/$CompanyId/inventory" -TimeoutSec 30
    if ($null -eq $r.company_id) { throw 'sem company_id' }
}

Try-Step 'daily snapshot create' {
    $r = Invoke-RestMethod -Method Post "$Base/retention/$CompanyId/daily-snapshot" -TimeoutSec 60
    if (-not $r.snapshot_date) { throw 'sem snapshot_date' }
}

Try-Step 'financial summary' {
    $r = Invoke-RestMethod "$Base/financials/$CompanyId/summary" -TimeoutSec 30
    if (-not $r.available) { throw 'financials unavailable' }
}

Try-Step 'X-Request-ID header' {
    $resp = Invoke-WebRequest "$Base/api/v1/health/" -UseBasicParsing -TimeoutSec 10
    if (-not $resp.Headers['X-Request-ID']) { throw 'header ausente' }
}

Write-Host ''
Write-Host '=== Resumo Fase A smoke ==='
$results | Format-Table -AutoSize
$fail = @($results | Where-Object { $_.Status -eq 'FAIL' }).Count
if ($fail -gt 0) { exit 1 }
exit 0
