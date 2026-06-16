"""
JUNO Ledger - Agendador do fechamento de lotes (APScheduler).

Tres jeitos de usar:

1) Dentro do FastAPI (recomendado no Railway) — lifespan:

    from contextlib import asynccontextmanager
    from juno_audit.scheduler import build_scheduler

    @asynccontextmanager
    async def lifespan(app):
        scheduler = build_scheduler(SessionLocal,
                                    agent_private_key=os.environ.get("JUNO_AGENT_SK"))
        scheduler.start()
        yield
        scheduler.shutdown(wait=False)

    app = FastAPI(lifespan=lifespan)

2) Processo separado (on-prem / Docker):

    python -m juno_audit.scheduler --db "postgresql://..." --loop

3) Execucao unica (manual / cron / Task Scheduler do Windows):

    python -m juno_audit.scheduler --db "postgresql://..." --once

NOTA RAILWAY: se o backend rodar com mais de 1 replica/worker, use um
advisory lock para o job nao rodar em dobro:
    SELECT pg_try_advisory_lock(7242026)  -- pula o ciclo se ja ha um rodando
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from .anchors import OpenTimestampsBackend
from .batch import close_open_batches, retry_pending, upgrade_submitted

log = logging.getLogger("juno_audit.scheduler")


def run_cycle(session_factory, backend=None, *, min_batch_size: int = 50,
              max_age_minutes: int = 60) -> dict:
    """Um ciclo completo: fecha lotes novos, reenvia pendentes, promove recibos."""
    backend = backend or OpenTimestampsBackend()
    closed = close_open_batches(session_factory, backend,
                                min_batch_size=min_batch_size,
                                max_age_minutes=max_age_minutes)
    resubmitted = retry_pending(session_factory, backend)
    confirmed = upgrade_submitted(session_factory, backend)
    summary = {"closed": len(closed), "resubmitted": resubmitted,
               "confirmed": confirmed, "batches": closed}
    log.info("ciclo: %s", {k: summary[k] for k in ("closed", "resubmitted", "confirmed")})
    return summary


def build_scheduler(session_factory, *, backend=None,
                    interval_minutes: int = 60,
                    min_batch_size: int = 50,
                    max_age_minutes: int = 60,
                    agent_private_key: Optional[str] = None) -> BackgroundScheduler:
    """Scheduler pronto: ciclo a cada `interval_minutes` (default 1h)."""
    backend = backend or OpenTimestampsBackend()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_cycle,
        trigger="interval",
        minutes=interval_minutes,
        args=[session_factory],
        kwargs={"backend": backend,
                "min_batch_size": min_batch_size,
                "max_age_minutes": max_age_minutes},
        id="juno_anchor_cycle",
        max_instances=1,          # nunca dois ciclos simultaneos no processo
        coalesce=True,            # se atrasar, roda 1 vez, nao acumula
        misfire_grace_time=600,
    )
    return scheduler


def _main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="juno-anchor")
    p.add_argument("--db", default=os.environ.get("DATABASE_URL"),
                   help="URL SQLAlchemy do Postgres (ou env DATABASE_URL)")
    p.add_argument("--once", action="store_true", help="roda um ciclo e sai")
    p.add_argument("--loop", action="store_true", help="roda continuamente")
    p.add_argument("--interval", type=int, default=60, help="minutos entre ciclos")
    p.add_argument("--min-batch", type=int, default=50)
    p.add_argument("--max-age", type=int, default=60, help="minutos")
    args = p.parse_args()

    if not args.db:
        p.error("--db ou DATABASE_URL e obrigatorio")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(args.db)
    SessionLocal = sessionmaker(bind=engine)

    if args.once:
        summary = run_cycle(SessionLocal,
                            min_batch_size=args.min_batch,
                            max_age_minutes=args.max_age)
        print(summary)
        return 0

    if args.loop:
        sched = build_scheduler(SessionLocal, interval_minutes=args.interval,
                                min_batch_size=args.min_batch,
                                max_age_minutes=args.max_age)
        sched.start()
        print(f"juno-anchor rodando (ciclo a cada {args.interval} min). Ctrl+C para sair.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            sched.shutdown()
        return 0

    p.error("use --once ou --loop")
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
