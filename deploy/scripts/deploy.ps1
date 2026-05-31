<#
.SYNOPSIS
    JUNO Deploy Script for Windows
#>
param(
    [ValidateSet("development", "staging", "production")]
    [string]$Environment = "staging"
)

$ErrorActionPreference = "Stop"

function Write-Success($text) { Write-Host "✅ $text" -ForegroundColor Green }
function Write-Info($text)    { Write-Host "ℹ️  $text" -ForegroundColor White }

Write-Host "🚀 Deploying JUNO to $Environment environment..." -ForegroundColor Cyan

# Load environment
$envFile = ".env.$Environment"
if (!(Test-Path $envFile)) {
    Write-Error "Environment file not found: $envFile"
    exit 1
}

# Parse .env file
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}

Write-Success "Environment loaded: $envFile"

# Deploy
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build

Write-Host "⏳ Waiting for services..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Health check
try {
    $health = Invoke-RestMethod -Uri "http://localhost:9050/health" -TimeoutSec 10
    Write-Success "Backend is healthy: $($health.version)"
} catch {
    Write-Error "Backend health check failed"
    exit 1
}

# Migrations
Write-Host "🔄 Running migrations..." -ForegroundColor Yellow
docker-compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

Write-Host "🎉 Deploy completed!" -ForegroundColor Green
Write-Host "   Backend: http://localhost:9050"
Write-Host "   Frontend: http://localhost:4000"
