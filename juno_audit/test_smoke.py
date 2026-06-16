"""Smoke test: cadeia, assinatura, adulteracao detectada, merkle + prova."""
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from juno_audit import (AuditLedger, Base, generate_keypair, verify_chain,
                        merkle_root, merkle_proof, verify_proof,
                        verify_event_signature)

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

sk, pk = generate_keypair()
ledger = AuditLedger(session_factory=SessionLocal, agent_private_key=sk)

# 1) grava 5 eventos de 1 tenant
for i in range(5):
    ledger.record(tenant_id="empresa-x", agent_id="juno-kpi-analyst:v1",
                  event_type="AI_DECISION",
                  input_payload={"i": i},
                  output_payload={"score": 70 + i},
                  model_ref={"provider": "anthropic", "model": "claude-sonnet-4-6"},
                  risk_class="BAIXO")

chain = ledger.export_chain("empresa-x")
ok, errs = verify_chain(chain)
assert ok, errs
print("1) cadeia integra: OK (5 eventos)")

# 2) assinaturas
assert all(verify_event_signature(ev, ev["agent_sig"], pk) for ev in chain)
print("2) assinaturas Ed25519: OK")

# 3) adulteracao e detectada
tampered = json.loads(json.dumps(chain))
tampered[2]["output_hash"] = "sha256:" + "f" * 64
ok2, errs2 = verify_chain(tampered)
assert not ok2 and len(errs2) >= 1
print("3) adulteracao detectada: OK ->", errs2[0])

# 4) merkle root + prova de inclusao
hashes = [ev["hash"] for ev in chain]
root = merkle_root(hashes)
proof = merkle_proof(hashes, 3)
assert verify_proof(hashes[3], proof, root)
assert not verify_proof(hashes[2], proof, root)
print("4) merkle root + prova de inclusao: OK")
print("   root:", root)

# 5) verificador CLI
with open("/tmp/export.json", "w") as f:
    json.dump(chain, f)
with open("/tmp/pubkeys.json", "w") as f:
    json.dump({"juno-kpi-analyst:v1": pk}, f)
print("5) arquivos para CLI gerados")
