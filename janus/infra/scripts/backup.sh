#!/bin/bash
# JUNO Backup Script - PostgreSQL + Arquivos

set -e

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}
S3_BUCKET=${AWS_S3_BUCKET:-}

mkdir -p $BACKUP_DIR

echo "[$(date)] Iniciando backup..."
echo "[$(date)] Backup PostgreSQL..."
pg_dump -h postgres -U $DB_USER -d $DB_NAME -F custom -f $BACKUP_DIR/db_$DATE.dump

echo "[$(date)] Compactando..."
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz -C $BACKUP_DIR db_$DATE.dump
rm $BACKUP_DIR/db_$DATE.dump

if [ -n "$S3_BUCKET" ]; then
    echo "[$(date)] Upload para S3..."
    aws s3 cp $BACKUP_DIR/backup_$DATE.tar.gz s3://$S3_BUCKET/backups/
fi

echo "[$(date)] Limpando backups antigos (>$RETENTION_DAYS dias)..."
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "[$(date)] Backup concluido: backup_$DATE.tar.gz"
