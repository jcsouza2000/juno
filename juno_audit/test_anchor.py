"""Smoke test Sprint 2: fechamento de lotes, idempotencia, retry e upgrade."""
import json
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from juno_audit import (AuditLedger, Base, generate_keypair, AuditAnchorRow,
                        ClientExportBackend, merkle_root)
from juno_audit.batch import close_open_batches, retry_pending, upgrade_submitted
from juno_audit.scheduler import run_cycle

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

sk, pk = generate_keypair()
ledger = AuditLedger(session_factory=SessionLocal, agent_private_key=sk)

# 60 eventos do tenant A (fecha por tamanho, min=50) e 3 do tenant B (nao fecha)
for i in range(60):
    ledger.record(tenant_id="empresa-a", agent_id="juno-kpi-analyst:v1",
                  event_type="AI_DECISION", input_payload={"i": i},
                  output_payload={"score": i}, risk_class="BAIXO")
for i in range(3):
    ledger.record(tenant_id="empresa-b", agent_id="juno-kpi-analyst:v1",
                  event_type="AI_DECISION", input_payload={"i": i},
                  output_payload={"score": i}, risk_class="BAIXO")

backend = ClientExportBackend(agent_private_key=sk)

# 1) fecha lote do tenant A; tenant B fica de fora (3 < 50 e recente)
r1 = close_open_batches(SessionLocal, backend, min_batch_size=50, max_age_minutes=60)
assert len(r1) == 1 and r1[0]["tenant_id"] == "empresa-a" and r1[0]["events"] == 60
print("1) lote fechado por tamanho (60 eventos, tenant A): OK")

# 2) idempotencia: segunda rodada nao cria nada
r2 = close_open_batches(SessionLocal, backend, min_batch_size=50, max_age_minutes=60)
assert r2 == []
print("2) idempotencia (2a rodada sem lotes novos): OK")

# 3) tenant B fecha por idade (max_age=0 forca)
r3 = close_open_batches(SessionLocal, backend, min_batch_size=50, max_age_minutes=0)
assert len(r3) == 1 and r3[0]["tenant_id"] == "empresa-b" and r3[0]["events"] == 3
print("3) lote fechado por idade (3 eventos, tenant B): OK")

# 4) raiz da ancora bate com a raiz recalculada da cadeia exportada
chain_a = ledger.export_chain("empresa-a")
with SessionLocal() as s:
    anchor_a = s.execute(select(AuditAnchorRow).where(
        AuditAnchorRow.tenant_id == "empresa-a")).scalar_one()
    assert anchor_a.merkle_root == merkle_root([e["hash"] for e in chain_a])
    assert anchor_a.status == "EXPORTED" and anchor_a.anchor_receipt
    receipt = json.loads(anchor_a.anchor_receipt)
    assert receipt["merkle_root"] == anchor_a.merkle_root and "signature" in receipt
print("4) raiz da ancora confere com a cadeia + recibo assinado: OK")

# 5) novos eventos apos a ancora -> novo lote pega so o delta
for i in range(55):
    ledger.record(tenant_id="empresa-a", agent_id="juno-kpi-analyst:v1",
                  event_type="AI_DECISION", input_payload={"j": i},
                  output_payload={"s": i}, risk_class="BAIXO")
r5 = close_open_batches(SessionLocal, backend, min_batch_size=50, max_age_minutes=60)
assert len(r5) == 1 and r5[0]["events"] == 55
with SessionLocal() as s:
    anchors = s.execute(select(AuditAnchorRow).where(
        AuditAnchorRow.tenant_id == "empresa-a").order_by(AuditAnchorRow.id)).scalars().all()
    # ids sao globais (empresa-b ocupa 61-63): a garantia e nao-sobreposicao
    assert anchors[1].first_event_id > anchors[0].last_event_id
    assert anchors[0].event_count + anchors[1].event_count == len(ledger.export_chain("empresa-a"))
print("5) lote incremental (so o delta, sem sobreposicao): OK")

# 6) retry de PENDING_SUBMIT (simula falha de rede com backend que falha 1x)
class FlakyBackend:
    anchor_type = "OPENTIMESTAMPS"
    def __init__(self): self.calls = 0
    def submit(self, root):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("calendario fora do ar")
        return b"fake-ots-receipt", "SUBMITTED"
    def upgrade(self, root, receipt):
        return b"fake-ots-receipt-btc", "CONFIRMED"

flaky = FlakyBackend()
for i in range(50):
    ledger.record(tenant_id="empresa-c", agent_id="a:v1",
                  event_type="AI_DECISION", input_payload={"i": i},
                  output_payload={}, risk_class="BAIXO")
rc = close_open_batches(SessionLocal, flaky, min_batch_size=50, max_age_minutes=60)
assert rc[0]["status"] == "PENDING_SUBMIT"          # falhou, mas lote registrado
n = retry_pending(SessionLocal, flaky)
assert n == 1
with SessionLocal() as s:
    a = s.execute(select(AuditAnchorRow).where(
        AuditAnchorRow.tenant_id == "empresa-c")).scalar_one()
    assert a.status == "SUBMITTED"
print("6) falha de rede -> PENDING_SUBMIT -> retry -> SUBMITTED: OK")

# 7) upgrade SUBMITTED -> CONFIRMED
n = upgrade_submitted(SessionLocal, flaky)
assert n == 1
with SessionLocal() as s:
    a = s.execute(select(AuditAnchorRow).where(
        AuditAnchorRow.tenant_id == "empresa-c")).scalar_one()
    assert a.status == "CONFIRMED" and a.confirmed_at is not None
print("7) upgrade SUBMITTED -> CONFIRMED com confirmed_at: OK")

# 8) run_cycle integrado (ciclo completo do scheduler)
for i in range(50):
    ledger.record(tenant_id="empresa-d", agent_id="a:v1",
                  event_type="AI_DECISION", input_payload={"i": i},
                  output_payload={}, risk_class="BAIXO")
summary = run_cycle(SessionLocal, backend=ClientExportBackend(sk),
                    min_batch_size=50, max_age_minutes=60)
assert summary["closed"] == 1
print("8) run_cycle (ciclo completo): OK ->", 
      {k: summary[k] for k in ("closed", "resubmitted", "confirmed")})

print("\nTODOS OS TESTES DO SPRINT 2 PASSARAM")
