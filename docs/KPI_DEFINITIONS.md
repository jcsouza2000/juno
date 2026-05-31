# Definicoes Canonicas de KPIs

Versao: `kpi-core-0.1`

Escopo atual: fundacao leve para desenvolvimento e primeiro piloto. Este documento nao substitui um contrato enterprise completo; ele define o minimo que nao pode divergir entre backend, frontend, relatorios e IA.

Este documento fixa as definicoes iniciais usadas nas telas executivas. Quando uma formula mudar, a alteracao deve acontecer primeiro no backend e depois ser refletida aqui.

## Score JUNO

Fonte canonica: `app.score_v2.JunoScoreCalculator`.

O Score JUNO exibido em APIs, catalogo de KPIs e aba Minha Empresa deve vir do Score v2. Placeholders ou calculos paralelos no frontend nao devem ser usados.

## Receita

Receita bruta: soma de `SalesOrder.revenue`.

Receita liquida: soma de `SalesOrder.revenue - SalesOrder.discount`.

Indicadores de margem, sazonalidade, concentracao de clientes e dashboards executivos devem usar receita liquida quando houver descontos registrados.

## Atraso

Uma ordem de producao esta atrasada quando:

- `actual_date > planned_date`, para ordens concluidas.
- `actual_date` esta vazio e `planned_date` ja passou, para ordens em aberto.

Percentual de atraso: `ordens_atrasadas / total_ordens_producao`.

## Cobertura de Dados

Cobertura de dados representa a quantidade de fontes essenciais carregadas contra o total esperado. A fonte inicial e o catalogo de KPIs em `app.kpi_catalog`.

O frontend deve exibir a cobertura calculada pelo backend, sem recalcular pesos ou fontes localmente.

## Regra de Evolucao

- Mudancas de formula devem ser feitas primeiro no backend.
- Mudancas em KPIs criticos devem atualizar este documento.
- Mudancas em Score JUNO, receita liquida, margem, atraso, liquidez ou cobertura devem atualizar os testes dourados.
- O frontend nao deve introduzir formula propria para KPI critico; deve consumir payload calculado pelo backend.

## Piloto

Antes do primeiro piloto comercial, esta fundacao deve evoluir para:

- Contratos de API revisados por endpoint critico.
- Dataset representativo do cliente piloto.
- Testes dourados com tolerancias aprovadas.
- Changelog de formula por versao.
