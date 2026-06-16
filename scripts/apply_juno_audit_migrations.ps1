# Aplica migrations.sql do juno_audit no Postgres (Railway ou local)
param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$SqlFile = (Join-Path (Split-Path $PSScriptRoot -Parent) "juno_audit\migrations.sql")
)

$ErrorActionPreference = "Stop"

if (-not $DatabaseUrl) {
    Write-Host "[FAIL] DATABASE_URL nao definida. Ex.:"
    Write-Host '  $env:DATABASE_URL="postgresql://user:pass@host:5432/db"'
    Write-Host '  powershell -File scripts\apply_juno_audit_migrations.ps1'
    exit 1
}

if (-not (Test-Path $SqlFile)) {
    Write-Host "[FAIL] SQL nao encontrado: $SqlFile"
    exit 1
}

$py = Join-Path (Split-Path $PSScriptRoot -Parent) "janus\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$script = @'
import sys
from pathlib import Path

from sqlalchemy import create_engine

url = sys.argv[1]
sql_path = Path(sys.argv[2])
raw = sql_path.read_text(encoding="utf-8")
engine = create_engine(url)
with engine.raw_connection() as conn:
    conn.cursor().execute(raw)
    conn.commit()
print("[OK] migrations.sql aplicado")
'@

& $py -c $script $DatabaseUrl $SqlFile
exit $LASTEXITCODE
