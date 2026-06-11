# Resultado da Validação E2E — JUNO Piloto (Fase A)

**Data:** 2026-06-10  
**Ambiente:** piloto local — SQLite `smart_juno.db`, empresa dev **ID 4** (Agora SA)

## Stack em execução

| Serviço | URL | Status |
|---------|-----|--------|
| Backend | http://127.0.0.1:8001 | OK (`ready=true`) |
| Frontend | http://localhost:4000 | OK (Next.js 16.2.6) |
| Ollama | http://127.0.0.1:11434 | OK (`qwen3:8b`) |
| Alembic | `daily_snapshots_table` | OK (head) |

**Subir stack:** `Smart_Juno.bat` ou manualmente backend `:8001` + `npm run dev -- --port 4000`.

---

## Smoke automatizado (API)

Script: `scripts/pilot_e2e_smoke.ps1`

```powershell
powershell -NoProfile -File C:\Souza\juno\scripts\pilot_e2e_smoke.ps1
```

| Passo | Resultado |
|-------|-----------|
| `GET /api/v1/health/ready` | OK |
| `GET /ai/ollama/health` | OK |
| `GET /kpis/4/unified` | OK |
| `GET /financials/4/valuation/scenario` | OK (EV > 0) |
| `GET /data/4/inventory` | OK |
| `POST /retention/4/daily-snapshot` | OK |
| `GET /financials/4/summary` | OK |
| Header `X-Request-ID` | OK |

**Resultado:** 8/8 OK (2026-06-10).

---

## Snapshot diário (job)

```powershell
cd C:\Souza\juno\janus\backend
$env:PYTHONPATH='.'
$env:DATABASE_URL='sqlite:///./smart_juno.db'
.\.venv\Scripts\python.exe ..\..\scripts\daily_snapshot_job.py
```

**Última execução:** 4 tenants, 3 criados, 1 atualizado, 0 erros.

**Agendamento (Task Scheduler — requer PowerShell como Administrador):**

```powershell
powershell -ExecutionPolicy Bypass -File C:\Souza\juno\scripts\schedule_daily_snapshot.ps1
```

Alternativa manual diária: `scripts\run_daily_snapshot.bat` (log em `logs/daily-snapshot.log`).

> Se `Register-ScheduledTask` retornar *Access is denied*, abra o terminal como Admin e rode o comando acima.

---

## Checklist manual (`docs/PILOT_E2E_CHECKLIST.md`)

| Item | Status | Notas |
|------|--------|-------|
| Health ready | OK | Automatizado |
| Login admin | Pendente UI | Dev bypass ativo em local |
| `/trust` | Pendente UI | |
| `/romi` tenant no header | Pendente UI | |
| `/executive` KPIs + comparativos | OK API | Validar visual no browser |
| Upload financeiro/ERP | Pendente UI | |
| PDF em `/romi` | Pendente UI | |
| `/ai` pergunta executiva | OK API/Ollama | Validar card valuation no browser |
| `/audit` eventos | Pendente UI | |
| Fluxo negativo (403/401) | Parcial | Coberto por testes pytest |
| PDF download | Pendente UI | |

---

## Testes pytest (pré-release)

```powershell
cd C:\Souza\juno\janus\backend
$env:PYTHONPATH='.'
$env:JUNO_ENV='development'
$env:SECRET_KEY='test-secret-key-must-have-at-least-32-chars'
$env:ENCRYPTION_KEY='N6zYqfBC2CxUgdztuLcM5nVSyxe7S6TjzS-ZmrkcmCM='
$env:DATABASE_URL='sqlite:///./validation.db'
.\.venv\Scripts\pytest -q --no-cov app/tests/test_comparativos.py app/tests/test_daily_snapshot.py app/tests/test_retention.py
```

---

## Critério Fase A

- [x] Migrations aplicadas (`daily_snapshots`)
- [x] Stack local sobe (backend + frontend + Ollama)
- [x] Smoke API 8/8
- [x] Job snapshot diário testado
- [x] Script de agendamento criado
- [ ] Checklist manual UI (demo com cliente)
- [ ] Playwright E2E (fase futura)

**Próxima fase:** **Fase B** — versionamento de uploads (v2/v3, versão ativa).
