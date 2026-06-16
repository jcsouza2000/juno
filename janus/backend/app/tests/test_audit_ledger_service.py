"""Guarda do servico de ledger (best-effort, gated a PostgreSQL).

Trava o contrato que protege o GET /score: em dev/SQLite a gravacao no ledger
e' no-op e NUNCA levanta — mesmo sem o pacote juno_audit instalado.
"""

from __future__ import annotations

from app.services import audit_ledger_service as svc


def test_audit_desabilitado_em_sqlite():
    # Conftest fixa DATABASE_URL=sqlite; o ledger deve ficar desabilitado.
    assert svc._audit_enabled() is False
    assert svc.get_audit_ledger() is None


def test_record_score_e_noop_sem_levantar():
    # Mesmo chamado, retorna None e nao propaga excecao (best-effort).
    out = svc.record_score_industrial(
        tenant_id="1",
        company_id=1,
        output_payload={"overall_score": 80},
    )
    assert out is None
