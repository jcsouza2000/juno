# juno_audit — Camada de Confiança do JUNO_AI (v0.2)

Implementa as Camadas 1 e 2 do blueprint, agora com o **Sprint 2 completo**:
**Ledger** (trilha encadeada por hash, por tenant), **Agent ID** (assinaturas
Ed25519), **verificador independente** (`juno-verify`) e **fechamento de
lotes com ancoragem** (Merkle + OpenTimestamps, gratuito, com slot
ICP-Brasil preparado).

Status: smoke tests completos passando — v0.1 (cadeia, assinaturas,
adulteração, Merkle, CLI) e v0.2 (lotes por tamanho e por idade,
idempotência, delta incremental, retry de rede, upgrade de recibo,
serialização `.ots` validada com a lib oficial).

## Estrutura

```
juno_audit/
  canonical.py     # JSON canônico + SHA-256 (base de tudo)
  chain.py         # build_event / verify_chain (prev_hash por tenant)
  signer.py        # Ed25519: generate_keypair / sign / verify (PyNaCl)
  merkle.py        # merkle_root / merkle_proof / verify_proof
  middleware.py    # AuditLedger (SQLAlchemy) — fachada p/ o FastAPI
  verify.py        # CLI juno-verify (candidato a repo público separado)
  models_anchor.py # tabela audit_anchors (com status do ciclo de vida)
  anchors.py       # backends: OpenTimestamps | ClientExport | ICP-Brasil(stub)
  batch.py         # fechamento de lotes: seleção, Merkle, retry, upgrade
  scheduler.py     # APScheduler (1h) + CLI juno-anchor (--once / --loop)
migrations.sql     # DDL v0.1 (audit_events + trigger append-only)
migrations_v2.sql  # DDL v0.2 (audit_anchors com status + índices + ALTERs)
test_smoke.py      # teste v0.1
test_anchor.py     # teste v0.2 (8 cenários)
test_ots_offline.py# valida serialização .ots com calendário simulado
```

## Ciclo de vida de uma âncora

`PENDING_SUBMIT` (lote fechado, rede falhou — retry automático) →
`SUBMITTED` (recibo `.ots` obtido; Bitcoin confirma em horas) →
`CONFIRMED` (atestado definitivo; `confirmed_at` preenchido).
O backend `ClientExportBackend` gera `EXPORTED` (pacote assinado para o
cofre do cliente — Opção C do blueprint).

## Instalação (Windows / PowerShell 5.1 / .venv311)

```powershell
Set-Location C:\Souza\juno\juno_audit
.\.venv311\Scripts\Activate.ps1
pip install pynacl apscheduler opentimestamps
# sqlalchemy você já tem no projeto
```

Aplicar `migrations_v2.sql` no Postgres (local Docker e, depois, Railway).
Se o `audit_anchors` do v0.1 já existe, os `ALTER TABLE ... IF NOT EXISTS`
do arquivo fazem a migração sem dor.

## Sprint 2 — rodando o fechamento de lotes

Execução manual (primeiro teste, com o Postgres local):

```powershell
$env:DATABASE_URL = "postgresql://user:pass@localhost:5432/juno"
python -m juno_audit.scheduler --once
```

Saída esperada: `{'closed': N, 'resubmitted': 0, 'confirmed': 0, ...}`.
Rode de novo: `closed: 0` (idempotente). Os recibos `.ots` ficam em
`audit_anchors.anchor_receipt`; a confirmação Bitcoin chega em algumas
horas — o próximo ciclo promove `SUBMITTED → CONFIRMED` sozinho.

Dentro do FastAPI no Railway (recomendado), no lifespan:

```python
from contextlib import asynccontextmanager
from juno_audit.scheduler import build_scheduler

@asynccontextmanager
async def lifespan(app):
    scheduler = build_scheduler(SessionLocal)   # ciclo a cada 60 min
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(lifespan=lifespan)
```

Parâmetros úteis de `build_scheduler` / `--once`: `min_batch_size=50`
(fecha lote ao atingir 50 eventos), `max_age_minutes=60` (ou quando o
evento pendente mais antigo passar de 1h — tenant de baixo volume também
é ancorado). Com mais de 1 réplica/worker no Railway, proteja o ciclo com
`pg_try_advisory_lock` (nota no `scheduler.py`).

## Gerar a identidade do primeiro agente

```powershell
python -c "from juno_audit.signer import generate_keypair; sk, pk = generate_keypair(); print('PRIVADA (cofre!):', sk); print('PUBLICA (registry):', pk)"
```

A privada vai para variável de ambiente / Railway secret `JUNO_AGENT_SK`.
**Nunca** no banco, nunca no git. A pública vai para o registro de agentes
e para o `pubkeys.json` distribuído com o verificador.

## Uso no FastAPI

```python
import os
from juno_audit import AuditLedger

ledger = AuditLedger(session_factory=SessionLocal,
                     agent_private_key=os.environ["JUNO_AGENT_SK"])

@router.post("/v31/score-industrial/{tenant_id}")
async def score(tenant_id: str):
    resultado = calcular_score(tenant_id)
    ledger.record(
        tenant_id=tenant_id,
        agent_id="juno-kpi-analyst:v1",
        event_type="AI_DECISION",
        input_payload={"tenant": tenant_id},
        output_payload=resultado,
        model_ref={"provider": "anthropic", "model": "claude-sonnet-4-6"},
        risk_class="BAIXO",
    )
    return resultado
```

## Verificação independente (o que o cliente roda)

```powershell
# exportar a cadeia de um tenant (endpoint a criar: GET /v31/audit/export)
python -m juno_audit.verify export.json --pubkeys pubkeys.json --root sha256:...
```

Saída esperada: `RESULTADO: TRILHA INTEGRA`.

## Teste

```powershell
python test_smoke.py
```

## Próximos passos (Sprint 3 do blueprint)

1. **Agent Registry** como tabela + endpoint (manifests versionados,
   chaves públicas, escopos) — hoje a chave pública vive só no
   `pubkeys.json` do verificador.
2. **Endpoint de export** `GET /v31/audit/export/{tenant_id}` (cadeia +
   âncoras + recibos) para alimentar o `juno-verify` do cliente.
3. **Carimbo ICP-Brasil** (RFC 3161): implementar o `IcpBrasilTsaBackend`
   (roteiro na docstring) quando contratar a ACT — Fase B.
4. **Tela "Auditoria" no Flutter** mostrando cadeia, âncoras e status —
   a demo de venda.
5. Separar `verify.py` num repositório público `juno-verify`.

## Avisos honestos

- O trigger append-only protege contra a aplicação, não contra um DBA
  malicioso — quem fecha esse buraco é a âncora externa (passo 2).
- Payloads completos não devem ir no evento: guarde só hashes no ledger e
  o conteúdo em storage WORM separado (LGPD: "crypto-shredding").
- Este é um esqueleto de engenharia, não uma opinião jurídica: valide a
  estratégia de validade probatória (ICP-Brasil) com seu advogado.
