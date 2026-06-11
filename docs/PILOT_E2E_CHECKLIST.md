# JUNO Pilot E2E Checklist

Checklist mínimo para provar confiança antes de demo com cliente ou piloto pago.

**Evidências automatizadas:** `scripts/pilot_e2e_smoke.ps1` (10 passos API)  
**Registro de execução:** `docs/E2E_VALIDATION_RESULT.md`  
**Produção:** `docs/PROD_HARDENING_CHECKLIST.md`

## Escopo mínimo

Execute este fluxo sempre que houver mudança em autenticação, tenant, importação, IA, PDF, versionamento, comparativos ou deploy.

## Preparação

- [ ] Backend rodando e `/api/v1/health/ready` retornando `ready=true`
- [ ] Frontend rodando em `http://localhost:4000`
- [ ] Ollama em `http://127.0.0.1:11434` (se testar IA)
- [ ] Smoke API: `powershell -File scripts\pilot_e2e_smoke.ps1` → **10/10 OK**
- [ ] Usuário admin de tenant criado (ou login real em staging/prod)
- [ ] Usuário comum criado no mesmo tenant
- [ ] Se houver dois tenants, usuário comum não deve ter acesso ao segundo

## Fluxo principal (UI)

Marque após validar no browser:

- [ ] **1. Login** como admin
- [ ] **2. `/trust`** — postura de confiança carrega
- [ ] **3. `/romi`** — nome do tenant no header
- [ ] **4. `/executive`** — KPIs + relatório Templates
- [ ] **5. `/executive` → aba Cenários** — matriz Actual/Budget/Projection/Valuation; Budget com metas reais (ex.: receita ~21.350 mi)
- [ ] **6. Upload** financeiro em `/financials` (2º upload gera v2)
- [ ] **7. `/data` (Meus Dados)** — coluna Versão, selo Ativa, botão Ativar em versões antigas
- [ ] **8. Ativar versão** anterior e confirmar KPIs refletem o lote escolhido
- [ ] **9. PDF** em `/romi` — download OK
- [ ] **10. `/ai`** — pergunta executiva; resposta não executa ação sem confirmação; card valuation se aplicável
- [ ] **11. `/audit`** — eventos recentes visíveis
- [ ] **12. Logout**

## Templates Orçamento / Budget

- [ ] **Demonstrações** — links visíveis: template realizado, Orçamento 2025, Budget 2025
- [ ] Download `template_demonstracoes_orcamento.xlsx` abre sem erro
- [ ] Coluna **Orçamento** presente no workbook `Templates/Demonstrações Financeiras_Templates.xlsx`

## Fluxo negativo de confiança

- [ ] Login como usuário comum
- [ ] `/trust` mostra restrição para postura em tempo real
- [ ] Menu admin/autoteste não aparece
- [ ] Tentar acessar dados de outro tenant via URL/API → **403**
- [ ] Chamadas sem token → **401** (com bypass desligado)

## Critério de aprovação

- [ ] Nenhum erro 500 nas rotas testadas
- [ ] Dados de um tenant não aparecem em outro
- [ ] PDF baixa corretamente
- [ ] IA não executa ação sensível sem confirmação
- [ ] Logs possuem `X-Request-ID` nas chamadas testadas
- [ ] Versionamento: upload não apaga silenciosamente versão anterior
- [ ] Comparativos por cenário auditáveis (nota de rodapé na aba Cenários)

## Quando automatizar

Automatize com Playwright quando:

- houver primeiro piloto com dados reais em produção;
- o login/tenant mudar de novo;
- o projeto ganhar deploy contínuo;
- houver cliente exigindo evidência recorrente.
