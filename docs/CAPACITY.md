# Capacidade e Escala — JUNO (Fase 6)

Documento de referência sobre **limites de volume de dados** suportados pela
arquitetura atual e o **caminho de evolução** conforme o crescimento. Responde
diretamente à pergunta do roadmap: *"qual o maior volume de dados que podemos
operar?"*.

> Resumo executivo: a stack atual (FastAPI + PostgreSQL + Redis) opera com
> conforto até a faixa de **dezenas de GB por tenant** (centenas de milhões de
> linhas analíticas). Acima de ~1 TB por tenant, o JUNO deixa de ser o
> *armazém* e passa a ser a *camada analítica* sobre um data lake.

---

## 1. Arquitetura atual (baseline)

| Camada | Tecnologia | Papel |
|---|---|---|
| API | FastAPI (monolito) | Endpoints, regras, IA Coordinator |
| Banco | PostgreSQL (prod) / SQLite (dev) | Dados de negócio por tenant |
| Cache | Redis | Cache de KPIs e sessão |
| ORM | SQLAlchemy 2.0 + Alembic | Modelos e migrations |
| IA | Ollama (qwen3:8b) local | Diagnóstico sobre dados reais |

Isolamento multi-tenant: **toda tabela de negócio tem `company_id` indexado**.
Os dados ficam em tabelas relacionais (financeiro, ERP operacional) e os KPIs
derivados são recalculados sob demanda ou congelados via `MonthlyClose`
(Fase 5).

---

## 2. Limites por faixa de volume

| Volume por tenant | Viável hoje? | O que é necessário |
|---|---|---|
| **≤ 500 MB** (CSVs piloto) | ✅ Sim | SQLite local ou PostgreSQL. Sem ajustes. |
| **1–5 GB** | ✅ Sim | PostgreSQL + índices por `company_id` + import em batch. |
| **5–50 GB** | ✅ Sim, com tuning | Pool de conexões, Redis cache obrigatório, paginação em todas as listas, import assíncrono. |
| **50–500 GB** | ⚠️ Sim, com arquitetura | Particionamento por `company_id`/período, filas (Celery/RQ), object storage (S3) para arquivos brutos, réplicas de leitura. |
| **1 TB** | ❌ Não na stack atual | Data lake (S3) + OLAP (ClickHouse/BigQuery). JUNO consome agregados. |
| **5–10 TB** | ❌ Projeto separado | Plataforma de dados industrial; JUNO é a camada de visualização/IA, não o storage. |

### Recomendação prática para o piloto (Agora SA)
- **Operacional confortável:** até ~5 GB de CSVs + ~50 M de linhas financeiras analíticas.
- Acima disso: mover imports pesados para PostgreSQL + arquivos brutos em disco/S3 (nunca SQLite).

---

## 3. Gargalos conhecidos e mitigação

| Gargalo | Sintoma | Mitigação |
|---|---|---|
| Agregações ad-hoc (curva ABC, concentração) varrem a tabela inteira | Latência cresce linear com o volume | Materializar agregados; índices compostos `(company_id, period)`; cache Redis |
| `purge` e `inventory` (Fase 0+3) contam linha a linha | Lento em tabelas grandes | Contagens aproximadas (`reltuples`) ou agregados mantidos |
| Recalcular Score a cada request | CPU alta | `MonthlyClose` congela o período; cache do score corrente |
| Import síncrono no request HTTP | Timeout em arquivos grandes | Fila assíncrona (Celery) + status de progresso |
| SQLite em dev não suporta concorrência real | Locks | PostgreSQL em qualquer cenário multiusuário (ver Fase 1) |

---

## 4. Caminho de evolução (quando escalar)

```
Hoje (≤50 GB/tenant)         50–500 GB/tenant            ≥1 TB/tenant
┌─────────────────┐          ┌─────────────────┐         ┌──────────────────────┐
│ FastAPI         │          │ FastAPI + Celery│         │ FastAPI (camada IA)  │
│ PostgreSQL      │  ──────► │ PostgreSQL      │ ──────► │ ClickHouse / BigQuery│
│ Redis           │          │  particionado   │         │ S3 + dbt/Spark (ETL) │
│                 │          │ Redis + S3 bruto│         │ S3 (cold/Parquet)    │
└─────────────────┘          └─────────────────┘         └──────────────────────┘
```

1. **Particionar** as tabelas quentes (`sales_orders`, `erp_financials`,
   `financial_statements`) por `company_id` e/ou faixa de período.
2. **Filas** (Celery + Redis) para import, recálculo de score e exports.
3. **Object storage** (S3/Azure Blob) para arquivos brutos e exports anuais
   (`.zip` + Parquet) — alinhado à Fase 5.3 do roadmap.
4. **OLAP** (ClickHouse/BigQuery) quando as análises passarem a varrer bilhões
   de linhas; o JUNO consulta agregados, não o detalhe.
5. **Cold storage** com política de retenção (Fase 5.4): financeiro 7 anos,
   operacional 2 anos (LGPD).

---

## 5. Checklist de capacidade antes de onboarding de tenant grande

- [ ] Volume estimado por tipo de dado (financeiro vs ERP operacional).
- [ ] PostgreSQL com `company_id` indexado em todas as tabelas de negócio.
- [ ] Redis ativo e cache de KPIs ligado.
- [ ] Import via batch/fila (não no request HTTP) para arquivos > 50 MB.
- [ ] Paginação aplicada em todos os endpoints de listagem.
- [ ] Política de retenção e fechamento mensal (`MonthlyClose`) definidos.
- [ ] Plano de backup (snapshot diário + arquivo anual) — Fase 5.

---

_Referência viva. Atualize as faixas conforme medições reais de produção._
