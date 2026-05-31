#!/bin/bash
# JUNO Restore Script

set -e

BACKUP_DIR="/backups"

if [ -z "$1" ]; then
    echo "Uso: $0 <arquivo_backup.tar.gz>"
    echo "Backups disponiveis:"
    ls -la $BACKUP_DIR/backup_*.tar.gz 2>/dev/null || echo "Nenhum backup encontrado"
    exit 1
fi

BACKUP_FILE=$1

echo "[$(date)] Iniciando restore de $BACKUP_FILE..."

tar -xzf $BACKUP_FILE -C $BACKUP_DIR
DB_FILE=$(ls $BACKUP_DIR/*.dump | head -1)

echo "[$(date)] Restaurando banco de dados..."
pg_restore -h postgres -U $DB_USER -d $DB_NAME --clean --if-exists $DB_FILE

rm $DB_FILE

echo "[$(date)] Restore concluido!"
