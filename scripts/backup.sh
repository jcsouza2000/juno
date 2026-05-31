#!/usr/bin/env bash
#
# JUNO - Backup automatizado do PostgreSQL
# Faz pg_dump do banco juno_db (container juno-postgres do docker-compose.prod),
# comprime, aplica retencao e, opcionalmente, envia para o S3.
#
# Uso:
#   ./scripts/backup.sh
#
# Variaveis de ambiente (opcionais):
#   BACKUP_DIR        diretorio local de backups        (padrao: ./backups)
#   RETENTION_DAYS    dias para manter backups locais   (padrao: 14)
#   COMPOSE_FILE      arquivo compose                   (padrao: docker-compose.prod.yml)
#   ENV_FILE          arquivo de env do compose         (padrao: .env.prod)
#   PG_SERVICE        nome do servico do Postgres       (padrao: juno-postgres)
#   PG_USER           usuario do Postgres               (padrao: juno)
#   PG_DB             nome do banco                      (padrao: juno_db)
#   S3_BUCKET         se definido, faz upload p/ s3://$S3_BUCKET/$S3_PREFIX/
#   S3_PREFIX         prefixo no bucket                  (padrao: juno/backups)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
PG_SERVICE="${PG_SERVICE:-juno-postgres}"
PG_USER="${PG_USER:-juno}"
PG_DB="${PG_DB:-juno_db}"
S3_PREFIX="${S3_PREFIX:-juno/backups}"

TS="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/juno_db_${TS}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] Gerando dump de '$PG_DB' via servico '$PG_SERVICE'..."
COMPOSE=(docker compose -f "$COMPOSE_FILE")
if [ -f "$ENV_FILE" ]; then
  COMPOSE+=(--env-file "$ENV_FILE")
fi

# pg_dump dentro do container, fluxo direto para gzip no host.
if ! "${COMPOSE[@]}" exec -T "$PG_SERVICE" \
      pg_dump -U "$PG_USER" -d "$PG_DB" --no-owner --no-privileges \
      | gzip > "$OUT"; then
  echo "[backup] ERRO: pg_dump falhou." >&2
  rm -f "$OUT"
  exit 1
fi

SIZE="$(du -h "$OUT" | cut -f1)"
echo "[backup] OK: $OUT ($SIZE)"

# Verificacao minima de integridade do gzip.
if ! gzip -t "$OUT"; then
  echo "[backup] ERRO: arquivo gzip corrompido." >&2
  exit 1
fi

# Upload opcional para S3 (usa AWS CLI / credenciais do ambiente).
if [ -n "${S3_BUCKET:-}" ]; then
  if command -v aws >/dev/null 2>&1; then
    echo "[backup] Enviando para s3://$S3_BUCKET/$S3_PREFIX/"
    aws s3 cp "$OUT" "s3://$S3_BUCKET/$S3_PREFIX/$(basename "$OUT")"
    echo "[backup] Upload concluido."
  else
    echo "[backup] AVISO: S3_BUCKET definido mas 'aws' nao encontrado. Pulando upload." >&2
  fi
fi

# Retencao local.
echo "[backup] Aplicando retencao: removendo backups locais com mais de ${RETENTION_DAYS} dias..."
find "$BACKUP_DIR" -name 'juno_db_*.sql.gz' -type f -mtime +"$RETENTION_DAYS" -print -delete || true

echo "[backup] Concluido."
