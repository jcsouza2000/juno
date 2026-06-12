#!/usr/bin/env python3
"""Gera .env.prod com segredos aleatorios (nao commitar o arquivo gerado)."""
from __future__ import annotations

import secrets
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".env.prod"

# Piloto local via Docker prod (portas 8002/4001). Troque dominios antes de go-live publico.
LINES = [
    "# JUNO Production — gerado por scripts/generate_env_prod.py",
    "# NUNCA commitar este arquivo.",
    "",
    "JUNO_ENV=production",
    "JUNO_DEV_AUTH_BYPASS=false",
    f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}",
    "# DATABASE_URL abaixo e informativo; docker-compose.prod.yml monta a URL interna.",
    "DATABASE_URL=postgresql://juno:PLACEHOLDER@juno-postgres:5432/juno_db",
    "REDIS_URL=redis://juno-redis:6379/0",
    f"SECRET_KEY={secrets.token_urlsafe(64)}",
    f"ENCRYPTION_KEY={Fernet.generate_key().decode()}",
    "ALLOWED_ORIGINS=http://localhost:4002",
    "LOGIN_RATE_LIMIT=5/minute",
    "LOG_FORMAT=json",
    "RUN_MIGRATIONS=true",
    "NEXT_PUBLIC_API_URL=http://localhost:8002",
    f"NEXTAUTH_SECRET={secrets.token_urlsafe(32)}",
    f"AUTH_SECRET={secrets.token_urlsafe(32)}",
]

text = "\n".join(LINES) + "\n"
# Substituir placeholder pela senha real do POSTGRES
pg = [ln for ln in LINES if ln.startswith("POSTGRES_PASSWORD=")][0].split("=", 1)[1]
text = text.replace("PLACEHOLDER", pg)

OUT.write_text(text, encoding="utf-8")
print(f"Gerado: {OUT}")
print("Execute: powershell -File scripts\\prod_hardening_check.ps1")
