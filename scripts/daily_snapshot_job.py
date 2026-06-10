#!/usr/bin/env python3
"""Job noturno: snapshot diario de KPIs/demonstracoes para todos os tenants (Fase 5).

Uso:
  cd janus/backend
  PYTHONPATH=. python ../../scripts/daily_snapshot_job.py

Agende via Task Scheduler (Windows) ou cron (Linux) para rodar 1x/dia.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "janus" / "backend"
sys.path.insert(0, str(BACKEND))

from app.database import SessionLocal  # noqa: E402
from app.services import retention as svc  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        result = svc.run_daily_snapshots_all_tenants(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if not result.get("errors") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
