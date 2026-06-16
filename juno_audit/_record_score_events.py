"""Grava eventos de score no ledger (uso local / Docker one-off)."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from juno_audit import AuditLedger


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL obrigatorio", file=sys.stderr)
        return 1

    base = os.environ.get("JUNO_API_BASE", "http://host.docker.internal:8002")
    email = os.environ.get("JUNO_ADMIN_EMAIL", "admin@juno.local")
    password = os.environ.get("JUNO_ADMIN_PASSWORD", "Admin123!")
    company_ids = [
        int(x.strip())
        for x in os.environ.get("COMPANY_IDS", "1").split(",")
        if x.strip()
    ]
    calls_per_company = int(os.environ.get("CALLS_PER_COMPANY", "1"))

    # Login
    body = urllib.parse.urlencode({"username": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{base}/auth/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.loads(resp.read().decode())["access_token"]

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    ledger = AuditLedger(session_factory=SessionLocal)

    for company_id in company_ids:
        tenant_id = str(company_id)
        for call in range(1, calls_per_company + 1):
            score_req = urllib.request.Request(
                f"{base}/score/{company_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(score_req, timeout=60) as resp:
                payload = json.loads(resp.read().decode())

            ev = ledger.record(
                tenant_id=tenant_id,
                agent_id="juno-kpi-analyst:v1",
                event_type="AI_DECISION",
                input_payload={
                    "company_id": company_id,
                    "tenant_id": tenant_id,
                    "call": call,
                },
                output_payload=payload,
                model_ref={"provider": "juno", "model": "score-v2"},
                risk_class="BAIXO",
            )
            print(
                f"tenant={tenant_id} call={call} "
                f"score={payload.get('overall_score')} hash={ev['hash'][:24]}..."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
