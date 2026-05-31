#!/usr/bin/env bash
#
# JUNO - Restore do PostgreSQL a partir de um dump .sql.gz
#
# Uso:
#   ./scripts/restore.sh backups/juno_db_20260530_120000.sql.gz
#
# ATENCAO: o restore SOBRESCREVE dados do banco alvo. Confirme antes.
#
# Variaveis (opcionais): mesmas do backup.sh (COMPOSE_FILE, ENV_FILE, PG_SERVICE, PG_USER, PG_DB).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FILE="${1:-}"
if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Uso: $0 <arquivo.sql.gz>" >&2
  echo "Backups disponiveis em ./backups:" >&2
  ls -1 backups/*.sql.gz 2>/dev/null || echo "  (nenhum encontrado)" >&2
  exit 1
fi

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
PG_SERVICE="${PG_SERVICE:-juno-postgres}"
PG_USER="${PG_USER:-juno}"
PG_DB="${PG_DB:-juno_db}"

# Verifica integridade antes de tocar no banco.
echo "[restore] Verificando integridade de $FILE..."
if ! gzip -t "$FILE"; then
  echo "[restore] ERRO: arquivo gzip corrompido. Abortando." >&2
  exit 1
fi

echo
echo "============================================================"
echo " ATENCAO: isto vai RESTAURAR e SOBRESCREVER o banco '$PG_DB'."
echo " Arquivo: $FILE"
echo "============================================================"
read -r -p "Digite 'CONFIRMAR' para prosseguir: " ANS
if [ "$ANS" != "CONFIRMAR" ]; then
  echo "[restore] Cancelado pelo usuario."
  exit 1
fi

COMPOSE=(docker compose -f "$COMPOSE_FILE")
if [ -f "$ENV_FILE" ]; then
  COMPOSE+=(--env-file "$ENV_FILE")
fi

echo "[restore] Restaurando..."
gunzip -c "$FILE" | "${COMPOSE[@]}" exec -T "$PG_SERVICE" \
  psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1

echo "[restore] Concluido."
