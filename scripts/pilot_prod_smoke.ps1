# Smoke prod Docker (auth real, bypass off)
param(
    [string]$Base = "http://127.0.0.1:8002",
    [int]$CompanyId = 1,
    [string]$Email = "admin@juno.local",
    [string]$Password = "Admin123!"
)

$results = New-Object System.Collections.Generic.List[object]

function Add-Result($name, $ok, $detail = '') {
    $results.Add([pscustomobject]@{ Step = $name; Status = $(if ($ok) { 'OK' } else { 'FAIL' }); Detail = $detail })
}

function Try-Step($name, [scriptblock]$Block) {
    try {
        & $Block
        Add-Result $name $true
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

Try-Step 'auth/me sem token -> 401' {
    try {
        Invoke-RestMethod "$Base/auth/me" -TimeoutSec 10 | Out-Null
        throw 'esperava 401'
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 401) { throw $_ }
    }
}

$token = $null
Try-Step 'auth/login admin' {
    $r = Invoke-RestMethod -Method Post "$Base/auth/login" -Body @{
        username = $Email
        password = $Password
    } -ContentType 'application/x-www-form-urlencoded' -TimeoutSec 15
    if (-not $r.access_token) { throw 'sem token' }
    $script:token = $r.access_token
}

$headers = @{ Authorization = "Bearer $token" }

Try-Step 'auth/me com token' {
    $r = Invoke-RestMethod "$Base/auth/me" -Headers $headers -TimeoutSec 10
    if ($r.email -ne $Email) { throw 'email incorreto' }
}

Try-Step 'data inventory autenticado' {
    $r = Invoke-RestMethod "$Base/data/$CompanyId/inventory" -Headers $headers -TimeoutSec 30
    if ($null -eq $r.company_id) { throw 'sem company_id' }
}

Try-Step 'X-Request-ID header' {
    $resp = Invoke-WebRequest "$Base/api/v1/health/" -UseBasicParsing -TimeoutSec 10
    if (-not $resp.Headers['X-Request-ID']) { throw 'header ausente' }
}

Write-Host ''
Write-Host '=== Smoke prod Docker (auth real) ==='
$results | Format-Table -AutoSize
$fail = @($results | Where-Object { $_.Status -eq 'FAIL' }).Count
if ($fail -gt 0) { exit 1 }
Write-Host "Todos OK ($($results.Count) passos)"
exit 0
