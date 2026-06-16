"""Smoke test do router FastAPI v31 (registry + export via HTTP)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from juno_audit import (AuditLedger, Base, generate_keypair,
                        ClientExportBackend)
# importacao explicita para registrar juno_agents no metadata antes do create_all
from juno_audit import registry  # noqa: F401
from juno_audit.batch import close_open_batches
from juno_audit.router import build_audit_router

# SQLite :memory: com StaticPool -> 1 conexao compartilhada entre threads
# (TestClient roda em thread separada). Em Postgres real isso nao se aplica.
engine = create_engine("sqlite:///:memory:",
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

juno_sk, _ = generate_keypair()
agent_sk, agent_pk = generate_keypair()

app = FastAPI()
app.include_router(build_audit_router(SessionLocal, juno_private_key=juno_sk))
client = TestClient(app)

# 1. POST /agents
r = client.post("/v31/audit/agents", json={
    "agent_id": "juno-kpi-analyst", "version": "1.0.0",
    "public_key": agent_pk,
    "manifest": {"purpose": "Score Industrial",
                 "model_ref": {"provider": "anthropic"},
                 "scopes": ["read:erp.financeiro"],
                 "denied": ["write:erp.*"], "risk_class": "BAIXO"},
})
assert r.status_code == 201, r.text
print("1) POST /agents -> 201 OK")

# 2. Duplicidade -> 409
r = client.post("/v31/audit/agents", json={
    "agent_id": "juno-kpi-analyst", "version": "1.0.0",
    "public_key": agent_pk,
    "manifest": {"purpose": "Score Industrial", "risk_class": "BAIXO"},
})
assert r.status_code == 409
print("2) POST /agents duplicado -> 409: OK")

# 3. GET /agents
r = client.get("/v31/audit/agents")
assert r.status_code == 200 and len(r.json()) == 1
print("3) GET /agents -> lista 1 agente: OK")

# 4. GET por id/version
r = client.get("/v31/audit/agents/juno-kpi-analyst/1.0.0")
assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
print("4) GET /agents/{id}/{ver} -> ACTIVE: OK")

# 5. DELETE -> revoga
r = client.delete("/v31/audit/agents/juno-kpi-analyst/1.0.0")
assert r.status_code == 200 and r.json()["status"] == "REVOKED"
print("5) DELETE /agents/{id}/{ver} -> REVOKED (nao apaga): OK")

# 6. Gera eventos e exporta bundle
ledger = AuditLedger(session_factory=SessionLocal, agent_private_key=agent_sk)
for i in range(55):
    ledger.record(tenant_id="empresa-x", agent_id="juno-kpi-analyst:1.0.0",
                  event_type="AI_DECISION", input_payload={"i": i},
                  output_payload={"score": i}, risk_class="BAIXO")
close_open_batches(SessionLocal, ClientExportBackend(juno_sk),
                   min_batch_size=50, max_age_minutes=60)

r = client.get("/v31/audit/export/empresa-x")
assert r.status_code == 200
assert "attachment" in r.headers["content-disposition"]
bundle = r.json()
assert bundle["summary"]["event_count"] == 55
assert bundle["summary"]["anchor_count"] == 1
print(f"6) GET /export/{{tenant}} -> bundle download "
      f"({len(r.content)} bytes, Content-Disposition correto): OK")

print("\nROUTER FASTAPI v31: TODOS OS TESTES PASSARAM")
