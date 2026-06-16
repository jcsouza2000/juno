# JUNO Audit v0.3 — Guia VSCode (Sprint 3 entregue)

Este guia assume seu setup: **Windows, PowerShell 5.1, `.venv311` (Python 3.11.9), VSCode, projeto em `C:\Souza\juno`, backend FastAPI em `janus/backend`, `juno_audit` como pacote instalado via Dockerfile.**

## O que tem de novo no v0.3

1. **Bugfix OTS**: `RemoteCalendar(url).submit(digest, timeout=...)` — não mais `(url, timeout=...).submit(digest)`. Era esse o `TypeError` mascarado como falha de rede no `PENDING_SUBMIT` do seu teste anterior.
2. **Bugfix `upgrade()`**: trata o retorno do `get_timestamp` que pode vir como bytes (commitment) em vez de `Timestamp` — destrava o ciclo `SUBMITTED → CONFIRMED`.
3. **`_safe_submit` agora loga `exc_info=True`**: nunca mais um bug de API silenciado como "rede".
4. **Agent Registry**: tabela `juno_agents`, endpoints REST, manifest versionado, revogação (sem delete), trigger Postgres de imutabilidade de identidade.
5. **Export bundle**: `GET /v31/audit/export/{tenant_id}` retorna arquivo único `juno-audit-<tenant>.json` (cadeia + âncoras + recibos `.ots` base64 + chaves públicas + provas de inclusão).
6. **`juno-verify` reforçado**: modo bundle automático, verifica integridade do bundle, recibos OpenTimestamps e atestados Bitcoin. Mantém modo legacy v0.1.

## Estrutura

```
juno_audit/
  __init__.py
  canonical.py        # JSON canônico + SHA-256
  chain.py            # build_event / verify_chain
  signer.py           # Ed25519
  merkle.py           # merkle_root / proof / verify
  middleware.py       # AuditLedger
  models_anchor.py    # tabela audit_anchors
  anchors.py          # OTS / ClientExport / ICP-Brasil(stub)   ← BUGFIX
  batch.py            # fechamento de lotes                     ← exc_info=True
  scheduler.py        # APScheduler + CLI
  verify.py           # juno-verify (bundle + legacy)           ← NOVO
  registry.py         # Agent Registry                          ← NOVO
  export.py           # build_export_bundle                     ← NOVO
  router.py           # FastAPI v31 (agents + export)           ← NOVO
migrations.sql        # v0.1
migrations_v2.sql     # v0.2
migrations_v3.sql     # v0.3 (juno_agents + triggers)           ← NOVO
test_smoke.py         # Sprint 1
test_anchor.py        # Sprint 2
test_ots_offline.py   # OTS com calendário simulado
test_sprint3.py       # Sprint 3                                ← NOVO
test_router.py        # FastAPI v31 via TestClient              ← NOVO
pyproject.toml
README.md
```

---

## 1. Atualizar a cópia local

Descompacte sobre `C:\Souza\juno\juno_audit\` (substitui os arquivos com bugfixes; mantém o `.venv311`).

```powershell
Set-Location C:\Souza\juno\juno_audit
.\.venv311\Scripts\Activate.ps1
pip install -e . --upgrade
pip install httpx fastapi pydantic   # para rodar os testes do router
```

## 2. Rodar TODOS os testes (sanidade local)

```powershell
python test_smoke.py
python test_anchor.py
python test_ots_offline.py
python test_sprint3.py
python test_router.py
```

Esperado: todos imprimem `PASSARAM` / `TRILHA INTEGRA`. Os `[FALHOU]` no Sprint 3 são o teste de detecção de adulteração — é o comportamento esperado.

## 3. Aplicar `migrations_v3.sql` no Postgres prod local

Mesmo padrão do v0.2 (a porta do Postgres não está publicada no host):

```powershell
docker exec -i juno-postgres psql -U juno -d juno_db < .\migrations_v3.sql
```

Esperado: cria `juno_agents`, índice parcial e dois triggers (`juno_agents_imutable`, `juno_agents_no_delete`).

## 4. Integrar o router no backend FastAPI

Em `janus/backend/app/main.py`, perto do `app.include_router(...)` que você já tem:

```python
import os
from juno_audit.router import build_audit_router

# Se já tem auth, passe a dependência aqui para proteger os endpoints:
# from app.deps import require_admin
# audit_router = build_audit_router(SessionLocal,
#                                   juno_private_key=os.environ.get("JUNO_AGENT_SK"),
#                                   dependencies=[Depends(require_admin)])

audit_router = build_audit_router(
    session_factory=SessionLocal,
    juno_private_key=os.environ.get("JUNO_AGENT_SK"),
)
app.include_router(audit_router)
```

**Importante**: em produção, esses endpoints devem exigir autenticação (export revela operação do cliente; registry cria identidades). O parâmetro `dependencies=[...]` aceita os `Depends` da sua auth existente.

## 5. Rebuild + restart do backend

```powershell
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend
docker compose -f docker-compose.prod.yml logs backend --tail 30
```

## 6. Validação fim a fim (este é o pitch ao vivo)

### 6.1 Registrar o agente do `/score`

Gere a chave pública correspondente à `JUNO_AGENT_SK` que já está rodando:

```powershell
python -c "from juno_audit.signer import generate_keypair; sk, pk = generate_keypair(); print('SK:', sk); print('PK:', pk)"
```

> Já tem chave em produção? Extraia só a pública dela:
> ```powershell
> python -c "import os, base64; from nacl.signing import SigningKey; sk = os.environ['JUNO_AGENT_SK'].split(':')[1]; print('ed25519:' + base64.b64encode(bytes(SigningKey(base64.b64decode(sk)).verify_key)).decode())"
> ```

Registre o agente:

```powershell
$body = @{
  agent_id = "juno-kpi-analyst"
  version  = "1.0.0"
  public_key = "ed25519:<COLE_A_PUBLICA>"
  manifest = @{
    purpose = "Score Industrial"
    model_ref = @{ provider = "anthropic"; model = "claude-sonnet-4-6" }
    scopes = @("read:erp.financeiro","read:erp.estoque")
    denied = @("write:erp.*","exec:pagamentos")
    risk_class = "BAIXO"
    owner = "ops@juno.ai"
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8002/v31/audit/agents" `
  -Body $body -ContentType "application/json"
```

### 6.2 Gerar uns eventos e fechar lote

```powershell
1..3 | ForEach-Object { Invoke-RestMethod "http://127.0.0.1:8002/score/1" | Out-Null }

# Fecha lote (mesmo comando do Sprint 2, agora com bugfix do timeout)
docker run --rm --network juno-prod-local_default `
  -v "C:\Souza\juno\juno_audit:/app/juno_audit" `
  -e PYTHONPATH=/app/juno_audit `
  -e DATABASE_URL="postgresql://juno:<SENHA>@juno-postgres:5432/juno_db" `
  python:3.11-slim bash -c "pip install -q -e /app/juno_audit && python -m juno_audit.scheduler --once --min-batch 1"
```

Desta vez deve sair `closed: 1, status: SUBMITTED` direto (sem `PENDING_SUBMIT`).

### 6.3 Baixar o bundle e verificar

```powershell
Invoke-RestMethod "http://127.0.0.1:8002/v31/audit/export/1" -OutFile bundle.json
python -m juno_audit.verify bundle.json
```

Saída esperada:

```
juno-verify  -  bundle mode  -  bundle.json

  [OK    ] [1] cadeia (N eventos)
  [OK    ] [2] assinaturas Ed25519 (N eventos assinados)
  [OK    ] [3] integridade do bundle (bundle_hash)
  [OK    ] [4] raizes Merkle (M ancoras)
  [OK    ] [5] provas de inclusao (X eventos)
  [OK    ] [6] recibos OpenTimestamps (Y .ots, Z confirmados no Bitcoin)

  RESULTADO: TRILHA INTEGRA
```

**Esse print é o pitch de venda.** Salve para a página /trust.

## 7. VSCode — atalhos úteis

### `.vscode/launch.json` (debug do scheduler --once)

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "juno-anchor --once (local)",
      "type": "debugpy",
      "request": "launch",
      "module": "juno_audit.scheduler",
      "args": ["--once", "--min-batch", "1"],
      "env": { "DATABASE_URL": "postgresql://juno:CHANGE_ME@localhost:5433/juno_db" },
      "console": "integratedTerminal"
    },
    {
      "name": "Testes (Sprint atual)",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/test_sprint3.py",
      "console": "integratedTerminal"
    }
  ]
}
```

### `.vscode/tasks.json`

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "JUNO: rodar todos os testes",
      "type": "shell",
      "command": "python test_smoke.py; python test_anchor.py; python test_ots_offline.py; python test_sprint3.py; python test_router.py",
      "group": { "kind": "test", "isDefault": true }
    }
  ]
}
```

---

## 8. Próximos passos sugeridos

1. **Tela "Auditoria" no Flutter**: lista cadeia + âncoras + status. Botão "Baixar bundle" chamando `/v31/audit/export/{tenant}`. Esta tela é a demo que fecha venda.
2. **Proteger os endpoints v31 com auth** (parâmetro `dependencies=` do `build_audit_router`).
3. **Migrar `tenant_id` de "1" para slug/UUID** antes de acumular mais cadeia.
4. **ICP-Brasil TSA** (Fase B do blueprint): implementar `IcpBrasilTsaBackend.submit()` quando contratar a ACT — o roteiro RFC 3161 está na docstring.
5. **CI**: adicionar workflow rodando os 5 testes a cada push.

## 9. Avisos honestos

- O bundle pode ficar grande para tenants antigos (proporcional à cadeia). Se virar problema, adicione paginação por janela de tempo no endpoint (`?since=...&until=...`).
- A trigger `juno_agents_imutable` deixa mudar só `status` e `revoked_at` — qualquer outra alteração levanta exceção no Postgres. Isso é proposital.
- Em produção com múltiplas réplicas: cuide do `pg_try_advisory_lock` no `scheduler.py` (nota lá dentro) para não rodar o job em paralelo.
- `manifest_sig` requer que `JUNO_AGENT_SK` esteja configurada quando o agente é registrado. Sem ela, o registro acontece, mas sem assinatura no manifest — bom para dev, fraco para produção.
