# Changelog do JUNO Industrial Diagnostic

Este arquivo consolida o histórico das fases de desenvolvimento do projeto.
Substitui os antigos `main_update_fase*.py` que foram removidos do código.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/).

## [Não publicado] — Trilíngue PT/EN/ES (Fase 2, fundação) 2026-06-07

### Adicionado (frontend)
- Camada de i18n leve via React Context (`src/lib/i18n.tsx`) — sem dependência
  externa nem reestruturação de rotas. Idioma persistido em localStorage e
  sincronizado entre abas.
- Dicionários `src/locales/{pt,en,es}.ts` com tipo `Dictionary` derivado do PT
  (en/es validados por estrutura no build).
- Seletor de idioma (PT/EN/ES) no Header.
- Telas traduzidas nos 3 idiomas: navegação (Sidebar), Header, "Meus Dados"
  (`/data`) e administração de usuários (`/admin/users`).

### Pendente (próximos incrementos da Fase 2)
- Traduzir `/executive`, `/financials`, `/integrations`, `/ai`.
- Backend: mensagens de API por `Accept-Language`; IA: SYSTEM_PROMPT por idioma.

## [Não publicado] — IA Operacional treinável (Fase 4) 2026-06-07

### Adicionado
- `app/analytics.py` — análises operacionais: `get_customer_concentration`
  (curva ABC de clientes + risco de dependência) e `get_product_abc` (curva
  ABC de produtos por receita). Somente leitura, escopadas por company_id.
- Duas novas ferramentas no Coordinator (`get_customer_concentration`,
  `get_product_abc`) com dispatch no caminho legado e labels de UI.
- `app/ai_playbook.yaml` + `app/ai_playbook.py` — playbook declarativo
  (pergunta → ferramenta → formato de resposta) injetado no SYSTEM_PROMPT.
  "Treina" a IA a escolher a ferramenta certa sem fine-tuning.
- `app/tests/test_analytics.py` (3 testes) e `app/tests/test_ai_playbook.py`
  (4 testes, incl. eval que falha se o playbook citar tool inexistente).

## [Não publicado] — Multi-usuário por tenant (Fase 1) 2026-06-07

### Adicionado
- `app/services/tenant_members.py` — CRUD de membros de tenant: vincular/criar
  usuário, alterar papel e remover, mantendo `user_companies` e
  `user_company_memberships` em sincronia. Protege o último owner (não pode ser
  rebaixado nem removido) e isola operações por `company_id`.
- `app/schemas/tenant.py` — papéis de tenant (owner/admin/member/viewer) e DTOs.
- `app/routers/tenant_users.py` — endpoints sob `/tenants/{company_id}/members`:
  - `GET` lista membros; `POST` convida/cria (gera senha temporária quando o
    usuário é novo e sem senha); `PATCH` altera papel; `DELETE` remove vínculo.
  - Autorização por papel no tenant (owner/admin) ou platform_admin.
- `app/tests/test_tenant_members.py` — 13 testes (criação, papéis, proteção do
  último owner, autorização e isolamento entre tenants).

## [Não publicado] — Gestão de dados do tenant (Fase 0+3) 2026-06-07

### Adicionado
- `app/data_management.py` — camada de "depósito de dados": inventário do que
  está persistido por grupo (financeiro, operacional ERP, KPIs derivados) e
  purge controlado por escopo. Reusa `FinancialUploadBatch` e `ERPImportBatch`
  como histórico de depósito (sem tabela/migration nova).
- `app/routers/data_management.py` — endpoints:
  - `GET /data/{company_id}/inventory` — "Meus dados" (contagens, períodos,
    histórico de uploads).
  - `POST /data/{company_id}/purge` — exclusão controlada (`financial` / `erp`
    / `all`), exigindo token de dupla confirmação `PURGE-{company_id}` e
    restrita a admin com acesso ao tenant. Nunca apaga usuários, vínculos,
    conexões ERP ou auditoria; remove tabelas-filho via FK antes dos pais.
- `app/tests/test_data_management.py` — 7 testes (inventário, isolamento por
  tenant, purge por escopo, FK dos filhos).

### IA / Multi-tenant
- `/ai/coordinator` passou a aceitar `company_id` no payload; o tenant da UI é
  autoritativo e sobrescreve o escolhido pelo modelo, sempre validado em
  `_resolve_company_id`. Em dev, `JUNO_DEV_COMPANY_ID` vincula o dev-user à
  empresa de demonstração.

## [Não publicado] — Auditoria e adequação 2026-05-14

### Segurança
- Removida `SECRET_KEY` hardcoded de `app/auth.py`. Agora vem de `Settings.SECRET_KEY` (env var), obrigatória em produção.
- Removidas credenciais de banco hardcoded em `app/database.py`. Fallback de dev passou a ser SQLite local, sem credenciais.
- CORS migrado de `allow_origins=["http://localhost:..."]` hardcoded para `ALLOWED_ORIGINS` via env var.
- Rate limiting (`slowapi`) ativado por padrão no endpoint `/auth/login` (5/minuto por IP, configurável via `LOGIN_RATE_LIMIT`).
- `docs` e `redoc` desabilitados automaticamente em produção.

### Adicionado
- `app/config.py` — Settings central com `pydantic-settings` e validação fail-fast.
- `app/core/logger.py` — logging estruturado (texto em dev, JSON em prod).
- `app/core/pagination.py` — helper `PaginationParams` + `paginate()` reutilizável.
- `.env.example` atualizado com todas as variáveis e instruções de geração de chave.

### Refatorado
- `app/main.py` reescrito para usar `Settings`, `slowapi`, logging estruturado e error handler que não vaza detalhes em prod.
- `app/routers/auth.py` agora aplica rate limit e loga tentativas (sucesso/falha).

### Removido
- `janus/app/` (backend legado completo): `main.py`, `ai.py`, `ontology.py`, `models.py`, `dashboard.py`, `core/`, `api/`, `integrations/`, `tests/`, `ai/` e os arquivos `main_update_fase10-12.py`.
- `app/main_update_fase5.py` até `app/main_update_fase9.py` — eram apenas documentação em forma de Python.
- `app/erp_connectors/` — diretório duplicado de conectores (`app/connectors/` é o oficial).

### Movido
- `janus/data/romi_products.csv`, `janus/data/fachini_products.csv` → `janus/examples/data/`.

---

## Fase 12 (anterior à auditoria) — AI/ML avançado

Adicionado ao `main.py` original (legado, em `janus/app/`):

```python
from app.api.rag import router as rag_router
from app.api.finetuning import router as finetuning_router
from app.api.agents import router as agents_router
from app.api.predictions import router as predictions_router

app.include_router(rag_router)
app.include_router(finetuning_router)
app.include_router(agents_router)
app.include_router(predictions_router)
```

## Fase 11 — Integrações (webhooks, ERP, CRM, payments, etc.)

```python
from app.api.webhooks import router as webhooks_router
from app.api.erp import router as erp_router
from app.api.crm import router as crm_router
from app.api.payments import router as payments_router
from app.api.public import router as public_router
from app.api.messaging import router as messaging_router
from app.api.etl import router as etl_router

for r in (webhooks_router, erp_router, crm_router, payments_router,
          public_router, messaging_router, etl_router):
    app.include_router(r)
```

## Fase 10 — Observabilidade (Sentry, OpenTelemetry, SLOs, Alerts)

```python
from app.core.telemetry import init_telemetry, get_tracer
from app.core.sentry import init_sentry
from app.api.slos import router as slos_router
from app.api.alerts import router as alerts_router

init_sentry()
init_telemetry(app)

app.include_router(slos_router)
app.include_router(alerts_router)
```

Middleware adicional de tracing por requisição (atributos `http.method`, `http.url`, `http.user_agent`, `http.status_code`).

## Fase 9 — Health check + métricas Prometheus

```python
from app.api.health import router as health_router
from prometheus_fastapi_instrumentator import Instrumentator

app.include_router(health_router)
Instrumentator().instrument(app).expose(app)
```

## Fase 8 — Segurança avançada (rate limit, security middleware)

```python
from app.api.security import router as security_router
from app.security.middleware import SecurityMiddleware, limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(security_router)
```

## Fase 7 — Relatórios

```python
from app.api.reports import router as reports_router
import os; os.makedirs("exports", exist_ok=True)
app.include_router(reports_router)
```

## Fase 6 — IA (predição, treino)

```python
from app.api.ai import router as ai_router
import os; os.makedirs("models", exist_ok=True)
app.include_router(ai_router)
```

## Fase 5 — Conectores ERP + scheduler

```python
from app.api.erp import router as erp_connectors_router
from app.schedulers import start_scheduler, stop_scheduler

app.include_router(erp_connectors_router)

@app.on_event("startup")
async def startup_event():
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    stop_scheduler()
```
