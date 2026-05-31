# JUNO Pilot E2E Checklist

Checklist minimo para provar confianca antes de demo com cliente ou piloto pago.

## Escopo minimo

Execute este fluxo sempre que houver mudanca em autenticacao, tenant, importacao, IA, PDF ou deploy.

## Preparacao

- Backend rodando e `/api/v1/health/ready` retornando `ready=true`.
- Frontend rodando em `http://localhost:4000`.
- Usuario admin de tenant criado.
- Usuario comum criado no mesmo tenant.
- Se houver dois tenants, usuario comum nao deve ter acesso ao segundo.

## Fluxo principal

1. Login como admin.
2. Abrir `/trust` e confirmar que a postura de confianca carrega.
3. Abrir `/romi` e confirmar que o nome do tenant aparece no header.
4. Abrir `/executive` e validar KPIs carregando para o tenant ativo.
5. Fazer upload de arquivo financeiro/ERP em `/integrations` ou `/financials`.
6. Gerar diagnostico e PDF em `/romi`.
7. Abrir `/ai`, fazer pergunta executiva e confirmar que a resposta nao executa acao sem confirmacao.
8. Abrir `/audit` e confirmar eventos recentes.
9. Fazer logout.

## Fluxo negativo de confianca

1. Login como usuario comum.
2. Confirmar que `/trust` mostra restricao para postura em tempo real.
3. Confirmar que menu de admin/autoteste nao aparece.
4. Tentar acessar dados de outro tenant via URL/API e esperar `403`.
5. Confirmar que chamadas sem token retornam `401`.

## Criterio de aprovacao

- Nenhum erro 500.
- Dados de um tenant nao aparecem em outro.
- PDF baixa corretamente.
- IA nao executa acao sensivel sem confirmacao.
- Logs possuem `X-Request-ID` para as chamadas testadas.

## Quando automatizar

Automatize este checklist com Playwright quando:

- houver primeiro piloto com dados reais;
- o login/tenant mudar de novo;
- o projeto ganhar deploy continuo;
- houver cliente exigindo evidencia recorrente.
