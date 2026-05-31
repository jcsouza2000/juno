# JUNO Trust Center

Este documento define a camada de confianca do JUNO para operar como SaaS hibrido B2B no Brasil.

## Principios

- Todo dado operacional pertence a um tenant (`company_id`).
- Toda rota sensivel deve exigir autenticacao e validacao de tenant.
- Acoes administrativas exigem `tenant admin` ou `platform_admin`.
- A IA deve explicar, registrar e pedir confirmacao antes de executar acao sensivel.
- LGPD, auditoria e seguranca precisam gerar evidencias consultaveis.

## Controles atuais

- Autenticacao JWT com usuario ativo.
- Separacao entre `admin` de tenant e `platform_admin`.
- Validacao de acesso por empresa nas rotas sensiveis.
- Segredos ERP criptografados em repouso e descriptografados apenas em runtime.
- Readiness probe com banco e Redis quando configurado.
- Request ID por resposta para rastreabilidade.
- Headers basicos de seguranca HTTP.
- Endpoint `/api/v1/security/trust/posture` para postura de confianca por tenant.

## Preparado agora, ativado quando fizer sentido

Estas pecas nao precisam virar custo agora, mas a arquitetura deve permitir adicionar sem refatoracao grande:

- MFA no login.
- SSO/OIDC ou SAML para clientes grandes.
- Refresh token, revogacao de sessao e politica de expiracao curta.
- Logs centralizados e alerta de falhas.
- Playwright ou equivalente para E2E automatizado.
- Storage externo criptografado para backups.

## Controles obrigatorios antes de cliente enterprise

- MFA no login.
- SSO/OIDC ou SAML para clientes grandes.
- Refresh token, revogacao de sessao e politica de expiracao curta.
- Testes E2E de login, tenant isolation, upload, IA, PDF e ERP.
- Backup e restore testados com registro de tempo de recuperacao.
- Logs estruturados centralizados e alerta de falhas.
- Runbook de incidente validado em simulacao.

## Fazer somente quando houver cliente ou exigencia contratual

- SOC 2 / ISO 27001 readiness formal.
- SSO/SAML por tenant.
- MFA obrigatorio por tenant.
- SLA contratual com multa/creditos.
- Monitoramento 24x7.

## LGPD

O JUNO deve manter por tenant:

- Registro de consentimentos.
- Requisicoes de titular (DSR).
- Base legal e finalidade de tratamento.
- Politica de retencao.
- Evidencia de exclusao/anonimizacao.
- Exportacao de dados do titular.

Pendente para maturidade alta:

- Bloquear processamento downstream quando consentimento for retirado.
- Expandir portabilidade para pedidos, chat, auditoria e dados derivados.
- Criptografar PII sensivel em repouso, nao apenas segredos ERP.

## IA governada

Toda recomendacao de IA deve preservar:

- Pergunta original.
- Fontes/dados usados.
- Ferramentas chamadas.
- Resposta gerada.
- Acao proposta.
- Usuario que confirmou.
- Resultado da execucao.

Acoes com impacto operacional devem exigir confirmacao humana.

## Operacao

Metas minimas:

- RPO inicial: 24 horas.
- RTO inicial: 4 horas.
- Uptime alvo inicial: 99,5%.
- Smoke test obrigatorio apos deploy.
- Rollback documentado para aplicacao e migrations.

## Certificacoes-alvo

- Fase 1: LGPD-ready com evidencias internas.
- Fase 2: ISO 27001 readiness.
- Fase 3: SOC 2 readiness para clientes enterprise.

## Criterio de confianca

Uma funcionalidade so deve ser considerada pronta para cliente externo quando tiver:

- Controle de acesso.
- Isolamento por tenant.
- Auditoria.
- Tratamento de erro observavel.
- Teste positivo e negativo.
- Documentacao operacional minima.
