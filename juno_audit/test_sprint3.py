"""Smoke test Sprint 3: Agent Registry + Export Bundle + Verify."""
import base64
import json
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from juno_audit import (AuditLedger, Base, generate_keypair, register_agent,
                        list_agents, get_agent, revoke_agent,
                        pubkeys_snapshot, AgentAlreadyExists, AgentNotFound,
                        build_export_bundle, ClientExportBackend)
from juno_audit.batch import close_open_batches
from juno_audit.verify import verify_bundle

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# ============================================================
# Agent Registry
# ============================================================
juno_sk, juno_pk = generate_keypair()      # chave da JUNO (assina manifests)
agent_sk, agent_pk = generate_keypair()    # chave do agente kpi-analyst v1

manifest_v1 = {
    "purpose": "Score Industrial",
    "model_ref": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    "scopes": ["read:erp.financeiro"],
    "denied": ["write:erp.*"],
    "risk_class": "BAIXO",
    "owner": "ops@juno.ai",
}

with SessionLocal() as s:
    row = register_agent(s, agent_id="juno-kpi-analyst", version="1.0.0",
                         public_key=agent_pk, manifest=manifest_v1,
                         juno_private_key=juno_sk)
    assert row.status == "ACTIVE" and row.manifest_sig
    print("1) registro de agente: OK")

# Duplicidade rejeitada
with SessionLocal() as s:
    try:
        register_agent(s, agent_id="juno-kpi-analyst", version="1.0.0",
                       public_key=agent_pk, manifest=manifest_v1)
        sys.exit("FALHOU: deveria rejeitar duplicidade")
    except AgentAlreadyExists:
        print("2) duplicidade (agent_id+version) rejeitada: OK")

# Versao 2 = identidade nova
agent2_sk, agent2_pk = generate_keypair()
manifest_v2 = {**manifest_v1, "risk_class": "MODERADO"}
with SessionLocal() as s:
    row2 = register_agent(s, agent_id="juno-kpi-analyst", version="2.0.0",
                          public_key=agent2_pk, manifest=manifest_v2)
    assert row2.id != row.id
    agents = list_agents(s)
    assert len(agents) == 2
    print("3) versao nova = identidade nova (2 agentes registrados): OK")

# Revogacao
with SessionLocal() as s:
    revoke_agent(s, "juno-kpi-analyst", "1.0.0")
    actives = list_agents(s, only_active=True)
    assert len(actives) == 1 and actives[0].version == "2.0.0"
    print("4) revogacao: v1.0.0 REVOKED, v2.0.0 ainda ACTIVE: OK")

# pubkeys_snapshot
with SessionLocal() as s:
    snap = pubkeys_snapshot(s)
    assert "juno-kpi-analyst:1.0.0" in snap
    assert "juno-kpi-analyst:2.0.0" in snap
    print(f"5) snapshot de chaves publicas: OK ({len(snap)} entradas)")

# ============================================================
# Eventos + ancoras + export bundle
# ============================================================
ledger = AuditLedger(session_factory=SessionLocal,
                     agent_private_key=agent2_sk)
for i in range(60):
    ledger.record(tenant_id="empresa-x",
                  agent_id="juno-kpi-analyst:2.0.0",
                  event_type="AI_DECISION",
                  input_payload={"i": i},
                  output_payload={"score": 70 + i},
                  risk_class="BAIXO")

close_open_batches(SessionLocal, ClientExportBackend(agent_private_key=juno_sk),
                   min_batch_size=50, max_age_minutes=60)
for i in range(10):  # 10 eventos pendentes (nao fecharam ainda)
    ledger.record(tenant_id="empresa-x", agent_id="juno-kpi-analyst:2.0.0",
                  event_type="AI_DECISION", input_payload={"i": i + 100},
                  output_payload={"score": i}, risk_class="BAIXO")

with SessionLocal() as s:
    bundle = build_export_bundle(s, "empresa-x")

assert bundle["summary"]["event_count"] == 70
assert bundle["summary"]["anchor_count"] == 1
assert bundle["summary"]["events_in_open_batch"] == 10
assert len(bundle["proofs"]) == 60  # so eventos ja ancorados tem prova
print(f"6) export bundle: 70 eventos, 1 ancora, 10 abertos, 60 provas: OK")

# Salva o bundle para o juno-verify
with open("/tmp/bundle.json", "w") as f:
    json.dump(bundle, f, ensure_ascii=False)
print(f"7) bundle salvo: {len(json.dumps(bundle))} bytes")

# ============================================================
# Verify bundle (sem OTS, porque os recibos sao CLIENT_EXPORT aqui)
# ============================================================
print("\n--- juno-verify bundle ---")
ok = verify_bundle(bundle, check_ots=False)
assert ok, "bundle deveria estar integro"
print("\n8) verify_bundle: OK")

# ============================================================
# Adulteracao detectada
# ============================================================
bad = json.loads(json.dumps(bundle))
bad["events"][30]["output_hash"] = "sha256:" + "ff" * 32
print("\n--- juno-verify bundle ADULTERADO ---")
ok = verify_bundle(bad, check_ots=False)
assert not ok, "deveria detectar adulteracao"
print("\n9) adulteracao detectada: OK")

print("\nTODOS OS TESTES DO SPRINT 3 PASSARAM")
