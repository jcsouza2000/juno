# JUNO Pilot E2E Checklist

Checklist mínimo para provar confiança antes de demo com cliente ou piloto pago.

**Evidências automatizadas:**
- `scripts/pilot_e2e_smoke.ps1` — smoke piloto dev (10 passos, empresa ID 4)
- `scripts/pilot_checklist_api.ps1` — PDF, audit, templates, cenários (API)
- `scripts/pilot_prod_smoke.ps1` — smoke Docker prod com login real (6 passos)
**Registro de execução:** `docs/E2E_VALIDATION_RESULT.md`  
**Produção:** `docs/PROD_HARDENING_CHECKLIST.md` · **Go-live:** `docs/GO_LIVE.md`

## Escopo mínimo

Execute este fluxo sempre que houver mudança em autenticação, tenant, importação, IA, PDF, versionamento, comparativos ou deploy.

## Preparação

- [x] Backend rodando e `/api/v1/health/ready` retornando `ready=true` — 2026-06-12
- [x] Frontend rodando em `http://localhost:4000` — 2026-06-12
- [x] Ollama em `http://127.0.0.1:11434` (se testar IA) — online no piloto dev
- [x] Smoke API: `powershell -File scripts\pilot_e2e_smoke.ps1` → **10/10 OK** — 2026-06-12
- [x] Usuário admin de tenant criado (ou login real em staging/prod) — Docker prod: `admin@juno.local`
- [ ] Usuário comum criado no mesmo tenant
- [ ] Se houver dois tenants, usuário comum não deve ter acesso ao segundo

## Fluxo principal (UI)

Marque após validar no browser (rotas carregam HTTP 200 em dev e prod Docker — 2026-06-12):

- [ ] **1. Login** como admin — rota `/login` OK; login real validado em prod Docker
- [x] **2. `/trust`** — rota carrega (HTTP 200)
- [x] **3. `/romi`** — rota carrega (HTTP 200)
- [x] **4. `/executive`** — rota carrega (HTTP 200)
- [x] **5. `/executive` → aba Cenários** — matriz Actual/Budget validada via API (dev ID 4)
- [ ] **6. Upload** financeiro em `/financials` (2º upload gera v2)
- [x] **7. `/data` (Meus Dados)** — versionamento validado via API (dev)
- [ ] **8. Ativar versão** anterior e confirmar KPIs refletem o lote escolhido
- [x] **9. PDF** em `/romi` — download OK via API `/reports/pdf/{id}`
- [x] **10. `/ai`** — rota carrega (HTTP 200); confirmação de ação pendente no browser
- [x] **11. `/audit`** — eventos via API `/audit/logs` OK
- [ ] **12. Logout**

## Templates Orçamento / Budget

- [x] **Demonstrações** — links visíveis: template realizado, Orçamento 2025, Budget 2025 — API HTTP 200
- [x] Download `template_demonstracoes_orcamento.xlsx` abre sem erro — validado via API
- [x] Coluna **Orçamento** presente no workbook `Templates/Demonstrações Financeiras_Templates.xlsx`

## Fluxo negativo de confiança

- [ ] Login como usuário comum
- [ ] `/trust` mostra restrição para postura em tempo real
- [ ] Menu admin/autoteste não aparece
- [ ] Tentar acessar dados de outro tenant via URL/API → **403**
- [ ] Chamadas sem token → **401** (com bypass desligado) — OK no Docker prod (`pilot_prod_smoke.ps1`)

## Critério de aprovação

- [x] Nenhum erro 500 nas rotas testadas (API checklist 2026-06-12)
- [ ] Dados de um tenant não aparecem em outro
- [x] PDF baixa corretamente — API `/reports/pdf/{id}` OK
- [ ] IA não executa ação sensível sem confirmação
- [x] Logs possuem `X-Request-ID` nas chamadas testadas
- [x] Versionamento: upload não apaga silenciosamente versão anterior — Fase B + smoke
- [x] Comparativos por cenário auditáveis (nota de rodapé na aba Cenários) — smoke + API

## Quando automatizar

Automatize com Playwright quando:

- houver primeiro piloto com dados reais em produção;
- o login/tenant mudar de novo;
- o projeto ganhar deploy contínuo;
- houver cliente exigindo evidência recorrente.
