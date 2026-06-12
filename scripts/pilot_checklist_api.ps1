# Validacao API do checklist manual (complementa browser)
param(
    [string]$Base = "http://127.0.0.1:8001",
    [int]$CompanyId = 4,
    [string]$Frontend = "http://localhost:4000"
)

$results = New-Object System.Collections.Generic.List[object]

function Add-Result($name, $ok, $detail = '') {
    $results.Add([pscustomobject]@{ Check = $name; Status = $(if ($ok) { 'OK' } else { 'FAIL' }); Detail = $detail })
}

function Try-Check($name, [scriptblock]$Block) {
    try {
        & $Block
        Add-Result $name $true
        Write-Host "[OK] $name"
    } catch {
        Add-Result $name $false $_.Exception.Message
        Write-Host "[FAIL] $name - $($_.Exception.Message)"
    }
}

Try-Check 'health/ready' {
    $r = Invoke-RestMethod "$Base/api/v1/health/ready" -TimeoutSec 10
    if (-not $r.ready) { throw 'ready=false' }
}

Try-Check 'auth/me (dev bypass ativo localmente)' {
    $r = Invoke-RestMethod "$Base/auth/me" -TimeoutSec 10
    if (-not $r.email) { throw 'sem usuario' }
}

Try-Check 'PDF preview' {
    $r = Invoke-RestMethod "$Base/reports/pdf/$CompanyId/preview" -TimeoutSec 60
    if (-not $r.available) { throw 'PDF indisponivel' }
}

Try-Check 'PDF download bytes' {
    $resp = Invoke-WebRequest "$Base/reports/pdf/$CompanyId" -UseBasicParsing -TimeoutSec 120
    if ($resp.RawContentLength -lt 100) {
        throw "tamanho invalido ($($resp.RawContentLength) bytes)"
    }
}

Try-Check 'audit logs' {
    $r = Invoke-RestMethod "$Base/audit/logs?company_id=$CompanyId&limit=5" -TimeoutSec 30
    if ($null -eq $r) { throw 'null' }
}

Try-Check 'comparativos cenario (Budget)' {
    $r = Invoke-RestMethod "$Base/financials/$CompanyId/comparativos/cenario" -TimeoutSec 60
    if ($r.cenarios.Count -lt 4) { throw 'cenarios incompletos' }
    $rec = $r.linhas | Where-Object { $_.indicador_key -eq 'receita_liquida' } | Select-Object -First 1
    if (-not $rec.valores.ORCAMENTO) { throw 'ORCAMENTO ausente' }
}

Try-Check 'data inventory version_label' {
    $r = Invoke-RestMethod "$Base/data/$CompanyId/inventory" -TimeoutSec 30
    $fin = @($r.uploads | Where-Object { $_.source -eq 'financial' })
    if ($fin.Count -gt 0 -and -not $fin[0].version_label) { throw 'version_label ausente' }
}

Try-Check 'template orcamento (frontend static)' {
    $code = (Invoke-WebRequest "$Frontend/templates/template_demonstracoes_orcamento.xlsx" -UseBasicParsing -TimeoutSec 15).StatusCode
    if ($code -ne 200) { throw "HTTP $code" }
}

Try-Check 'template budget (frontend static)' {
    $code = (Invoke-WebRequest "$Frontend/templates/template_demonstracoes_budget.xlsx" -UseBasicParsing -TimeoutSec 15).StatusCode
    if ($code -ne 200) { throw "HTTP $code" }
}

Try-Check 'X-Request-ID' {
    $resp = Invoke-WebRequest "$Base/api/v1/health/" -UseBasicParsing -TimeoutSec 10
    if (-not $resp.Headers['X-Request-ID']) { throw 'header ausente' }
}

Write-Host ''
Write-Host '=== Checklist API (complemento browser) ==='
$results | Format-Table -AutoSize
$fail = @($results | Where-Object { $_.Status -eq 'FAIL' }).Count
if ($fail -gt 0) { exit 1 }
Write-Host "Todos OK ($($results.Count) checks)"
exit 0
