"""
audit_retention.py - move audit_logs antigos para tabela cold storage.

Uso:
    python scripts/audit_retention.py --keep-days 365 [--dry-run]

Mantem os ultimos N dias na tabela quente (audit_logs); o resto vai para
audit_logs_archive (criada on-demand). Em prod recomendado agendar via cron/APScheduler:

    0 3 * * 0  python scripts/audit_retention.py --keep-days 365

Tabela archive nao tem indices alem da PK — pensada para queries raras.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

from sqlalchemy import text


def archive_old_audits(db, keep_days: int, dry_run: bool = False) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=keep_days)

    # Cria archive se nao existir
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS audit_logs_archive (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            user_name VARCHAR(255),
            action VARCHAR(100),
            source_table VARCHAR(100),
            details TEXT,
            ip_address VARCHAR(45),
            created_at DATETIME,
            archived_at DATETIME
        )
    """))

    # Conta linhas a arquivar
    count = db.execute(text(
        "SELECT COUNT(*) FROM audit_logs WHERE created_at < :cutoff"
    ), {"cutoff": cutoff}).scalar()

    summary = {"cutoff": cutoff.isoformat(), "rows_to_archive": int(count or 0), "dry_run": dry_run}

    if not count or dry_run:
        return summary

    # Move
    db.execute(text("""
        INSERT INTO audit_logs_archive
        (id, user_id, user_name, action, source_table, details, ip_address, created_at, archived_at)
        SELECT id, user_id, user_name, action, source_table, details, ip_address, created_at, :now
        FROM audit_logs WHERE created_at < :cutoff
    """), {"now": datetime.utcnow(), "cutoff": cutoff})

    db.execute(text(
        "DELETE FROM audit_logs WHERE created_at < :cutoff"
    ), {"cutoff": cutoff})
    db.commit()
    summary["rows_archived"] = int(count)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-days", type=int, default=365)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, ".")
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        result = archive_old_audits(db, args.keep_days, dry_run=args.dry_run)
        for k, v in result.items():
            print(f"  {k}: {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
