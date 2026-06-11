# Resultado da Validação E2E — JUNO Piloto

**Última atualização:** 2026-06-11  
**Ambiente:** piloto local — SQLite `smart_juno.db`, empresa dev **ID 4** (Agora SA)

## Stack em execução

| Serviço | URL | Status |
|---------|-----|--------|
| Backend | http://127.0.0.1:8001 | OK (`ready=true`) |
| Frontend | http://localhost:4000 | OK (Next.js 16.2.6) |
| Ollama | http://127.0.0.1:11434 | OK (`qwen3:8b`) |
| Alembic | `data_versioning_fase_b` | OK (head) |

**Subir stack:** `Smart_Juno.bat clean` (recomendado após mudanças) ou backend `:8001` + frontend `:4000`.

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

---

## Fases entregues

| Fase | Entrega | Commit |
|------|---------|--------|
| **A** | Smoke, snapshot diário, stack piloto | `e01cd9f` |
| **B** | Versionamento v1/v2, `/data`, ativar versão | `01d8d54` |
| **C** | Comparativos por cenário, aba Cenários | `e135b6c` |
| **C+** | Templates Orçamento/Budget, colunas no workbook canônico | pendente commit |

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
| Smoke API 10/10 | OK | Automatizado |
| `/executive` aba Cenários | OK UI | Budget 21.350 mi validado |
| `/data` versionamento | OK UI | v1–v4, Ativar |
| Templates Orçamento/Budget | OK | Links em `/financials` |
| Login admin real | Pendente | Dev bypass ativo em local |
| PDF `/romi` | Pendente UI | |
| `/audit` eventos | Pendente UI | |
| Fluxo negativo 401/403 | Parcial | pytest + staging prod |

---

## Hardening produção

Checklist: `docs/PROD_HARDENING_CHECKLIST.md`

```powershell
# Validar .env.prod antes do deploy
powershell -File scripts\prod_hardening_check.ps1 -EnvFile .env.prod.example
```

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

---

## Critério go-live piloto

- [x] Fases A, B, C no código e GitHub
- [x] Templates Orçamento/Budget
- [x] Smoke 10/10 (API)
- [x] Hardening checklist + script de validação
- [ ] Checklist manual UI 100% (demo cliente)
- [ ] `.env.prod` real + Docker prod testado
- [ ] Playwright E2E (fase futura)
