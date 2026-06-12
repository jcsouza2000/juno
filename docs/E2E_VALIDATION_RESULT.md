# Resultado da Validação E2E — JUNO Piloto

**Última atualização:** 2026-06-12 10:31 -04:00  
**Commit validado:** `6711391` + hardening Docker prod local  
**Ambiente dev:** SQLite `smart_juno.db`, empresa **ID 4** (Agora SA) — `:8001` / `:4000`  
**Ambiente prod local:** PostgreSQL Docker — `:8002` / `:4002`, admin `admin@juno.local`

## Stack em execução

| Serviço | URL | Status |
|---------|-----|--------|
| Backend | http://127.0.0.1:8001 | OK (`ready=true`) |
| Frontend | http://localhost:4000 | OK (Next.js 16.2.6) |
| Ollama | http://127.0.0.1:11434 | OK (`qwen3:8b`) |
| Alembic | `companies_created_at` | OK (head) |

**Subir piloto dev:** `Smart_Juno.bat clean` → backend `:8001` + frontend `:4000`.

**Subir prod local (Docker):**

```powershell
python scripts/generate_env_prod.py
powershell -File scripts/run_prod_docker_local.ps1
```

URLs: backend `http://localhost:8002`, frontend `http://localhost:4002`, admin `admin@juno.local` / `Admin123!`

---

## Smoke automatizado (API) — Fases A–C

Script: `scripts/pilot_e2e_smoke.ps1`

```powershell
powershell -NoProfile -File C:\Souza\juno\scripts\pilot_e2e_smoke.ps1
```

| # | Passo | Fase |
|---|-------|------|
| 1 | `GET /api/v1/health/ready` | A |
| 2 | `GET /ai/ollama/health` | A |
| 3 | `GET /kpis/4/unified` | A |
| 4 | `GET /financials/4/valuation/scenario` | A |
| 5 | `GET /data/4/inventory` | B |
| 6 | `POST /retention/4/daily-snapshot` | A |
| 7 | `GET /financials/4/summary` | A |
| 8 | `GET /financials/4/comparativos/cenario` | C |
| 9 | `data inventory version_label` | B |
| 10 | Header `X-Request-ID` | A |

**Resultado esperado:** 10/10 OK.

### Última execução — 2026-06-11 17:27 -04:00

Comando:

```powershell
powershell -NoProfile -File C:\Souza\juno\scripts\pilot_e2e_smoke.ps1
```

| # | Passo | Status |
|---|-------|--------|
| 1 | health/ready | OK |
| 2 | ollama health | OK |
| 3 | kpis unified | OK |
| 4 | valuation scenario | OK |
| 5 | data inventory | OK |
| 6 | daily snapshot create | OK |
| 7 | financial summary | OK |
| 8 | comparativos cenario | OK |
| 9 | data versions metadata | OK |
| 10 | X-Request-ID header | OK |

**Resultado:** **10/10 OK** (exit 0, ~21 s)

---

## Checklist API (complemento browser) — 2026-06-12

Script: `scripts/pilot_checklist_api.ps1`

```powershell
powershell -NoProfile -File C:\Souza\juno\scripts\pilot_checklist_api.ps1
```

**Resultado:** **10/10 OK** — health, auth/me, PDF, audit, comparativos Budget, version_label, templates, X-Request-ID.

---

## Smoke Docker prod (auth real) — 2026-06-12

Script: `scripts/pilot_prod_smoke.ps1`

```powershell
powershell -NoProfile -File C:\Souza\juno\scripts\pilot_prod_smoke.ps1
```

| Passo | Status |
|-------|--------|
| health/ready | OK |
| auth/me sem token → 401 | OK |
| auth/login admin | OK |
| auth/me com token | OK |
| data inventory autenticado | OK |
| X-Request-ID | OK |

**Resultado:** **6/6 OK** — PostgreSQL, `JUNO_DEV_AUTH_BYPASS=false`, login `admin@juno.local`.

---

## Fases entregues

| Fase | Entrega | Commit |
|------|---------|--------|
| **A** | Smoke, snapshot diário, stack piloto | `e01cd9f` |
| **B** | Versionamento v1/v2, `/data`, ativar versão | `01d8d54` |
| **C** | Comparativos por cenário, aba Cenários | `e135b6c` |
| **C+** | Templates Orçamento/Budget, colunas no workbook canônico | `9d59b54` |

---

## Orçamento real (Fase C+)

| Indicador | Actual | Budget (template) |
|-----------|--------|-------------------|
| Receita Líquida | 20.697,51 mi | 21.350,00 mi (+3,1% vs actual) |
| EBITDA | 7.848,12 mi | 8.050,00 mi |
| Lucro Líquido | 1.678,21 mi | 1.720,00 mi |

Documentação: `Templates/BUDGET_TEMPLATES.md`  
Regenerar: `python scripts/build_budget_templates.py`

---

## Snapshot diário (job)

```powershell
cd C:\Souza\juno\janus\backend
$env:PYTHONPATH='.'
$env:DATABASE_URL='sqlite:///./smart_juno.db'
.\.venv\Scripts\python.exe ..\..\scripts\daily_snapshot_job.py
```

Agendamento: `scripts\schedule_daily_snapshot.ps1` (requer PowerShell como Admin).

---

## Checklist manual UI

Arquivo: `docs/PILOT_E2E_CHECKLIST.md`

| Área | Status | Notas |
|------|--------|-------|
| Smoke API 10/10 | OK | 2026-06-12 — piloto dev |
| Checklist API 10/10 | OK | PDF, audit, templates, cenários |
| Docker prod smoke 6/6 | OK | auth real, PostgreSQL `:8002` |
| `/executive` aba Cenários | OK UI | Budget 21.350 mi validado |
| `/data` versionamento | OK UI | v1–v4, Ativar |
| Templates Orçamento/Budget | OK | Links em `/financials` |
| Login admin real | OK prod Docker | `admin@juno.local`; dev ainda usa bypass |
| PDF `/romi` | OK API | download `/reports/pdf/4` validado |
| `/audit` eventos | OK API | `/audit/logs` validado |
| Fluxo negativo 401/403 | Parcial | 401 sem token OK em prod Docker |

---

## Hardening produção

Checklist: `docs/PROD_HARDENING_CHECKLIST.md`

```powershell
powershell -NoProfile -File C:\Souza\juno\scripts\prod_hardening_check.ps1 -EnvFile C:\Souza\juno\.env.prod
```

**Prod local testado:** `run_prod_docker_local.ps1` + smoke `pilot_prod_smoke.ps1` (2026-06-12).

Requisitos críticos: `JUNO_ENV=production`, `JUNO_DEV_AUTH_BYPASS=false`, PostgreSQL, segredos ≥ 32 chars.

---

## Testes pytest (pré-release)

```powershell
cd C:\Souza\juno\janus\backend
$env:PYTHONPATH='.'
.\.venv\Scripts\pytest -q --no-cov `
  app/tests/test_data_versioning.py `
  app/tests/test_comparativos_cenario.py `
  app/tests/test_config.py
```

### Última execução — 2026-06-11 17:28 -04:00

Comando (escopo `test_config.py` do commit `9d59b54`):

```powershell
cd C:\Souza\juno\janus\backend
.\.venv\Scripts\python.exe -m pytest app\tests\test_config.py -q
```

| Teste | Status |
|-------|--------|
| `test_secret_key_required_in_production` | passed |
| `test_database_url_required_in_production` | passed |
| `test_dev_defaults_are_sane` | passed |
| `test_dev_auth_bypass_forbidden_in_production` | passed |
| `test_sqlite_forbidden_in_production` | passed |
| `test_cors_origins_parses_csv` | passed |

**Resultado:** **6 passed** (exit 0, ~5 s). 14 warnings matplotlib/pyparsing (sem falha).

---

## Critério go-live piloto

- [x] Fases A, B, C no código e GitHub
- [x] Templates Orçamento/Budget
- [x] Smoke 10/10 (API)
- [x] Hardening checklist + script de validação
- [ ] Checklist manual UI 100% (demo cliente) — fluxo browser 1–12 pendente
- [x] `.env.prod` + Docker prod testado localmente (`:8002` / `:4002`)
- [ ] Playwright E2E (fase futura)
- [ ] Go-live externo HTTPS — ver `docs/GO_LIVE.md`
