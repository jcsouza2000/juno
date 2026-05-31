# Tutorial: Adicionando seu Primeiro ObjectType

> **Tempo estimado:** 20 minutos
> **Pre-requisitos:** Backend rodando, `ONTOLOGY_ENABLED=true` no `.env`
> **Resultado:** novo tipo `Fornecedor` com 1 Action `aprovarFornecedor` —
>   exposta via REST, SDK Python, SDK TS e tools de IA, com auditoria automatica.

Este guia mostra o ciclo completo de adicao de uma entidade na ontologia. Quem
ja' adicionou um Object Type antes em sistemas como Foundry vai reconhecer o
fluxo: declarar → carregar → usar.

---

## Passo 1 — Crie o YAML

Coloque em `janus/backend/app/ontology/definitions/fornecedor.yaml`:

```yaml
apiVersion: ontology.juno.gravithy.com.br/v1
kind: ObjectType
metadata:
  name: Fornecedor
  description: |
    Fornecedor de insumos. Carrega rating, prazo medio de entrega
    e relacao com produtos.
  owner: compras
  tags: [compras, cadastro]

spec:
  backing:
    type: sqlalchemy
    model: app.models.Supplier
    primary_key: id

  title_property: name
  identifier_properties: [id]

  properties:
    id:
      type: integer
      required: true
      readonly: true
    company_id:
      type: integer
      required: true
      readonly: true
      marking: TenantScoped
    name:
      type: string
      required: true
      max_length: 255
    cnpj:
      type: cnpj
      marking: PII
    email:
      type: string
      max_length: 255
      marking: PII
    lead_time_days:
      type: integer
      min: 0
    rating:
      type: number
      min: 0
      max: 5
    status:
      type: enum
      enum_values: [active, inactive, blocked]

  computed_properties:
    confiavel:
      type: boolean
      formula: "rating >= 4 and lead_time_days <= 15"

  links:
    empresa:
      target: Empresa
      cardinality: many_to_one
      backing:
        type: foreign_key
        column: company_id

  markings:
    inherit: [TenantScoped]

  actions:
    - aprovarFornecedor

---
apiVersion: ontology.juno.gravithy.com.br/v1
kind: ActionType
metadata:
  name: aprovarFornecedor
  description: Marca um fornecedor como 'active' apos avaliacao de compliance.

spec:
  target: Fornecedor

  inputs:
    motivo:
      type: string
      required: true
      max_length: 500
    valido_ate:
      type: date
      required: false

  validation:
    - rule: "status == 'inactive' or status == 'blocked'"
      message: "Fornecedor ja' esta active."
      severity: error
    - rule: "rating >= 3"
      message: "Rating < 3 — aprovacao requer override de diretoria."
      severity: warning

  authorization:
    roles: [admin, comprador_senior, gerente_compras]
    require_confirmation: true

  effect:
    handler: app.ontology.actions.supplier.approve

  audit:
    fields_before: [status]
    fields_after: [status]
    extra_context: [motivo, valido_ate]

  dry_run: supported
```

## Passo 2 — Crie o handler Python

Em `janus/backend/app/ontology/actions/supplier.py`:

```python
"""Handlers para Actions sobre Fornecedor."""

from __future__ import annotations


def approve(target, inputs, *, db, user, cursor):
    """aprovarFornecedor: status -> 'active'."""
    target.status = "active"
    cursor.add_context("motivo", inputs["motivo"])
    if "valido_ate" in inputs:
        cursor.add_context("valido_ate", inputs["valido_ate"])
```

> O handler so' MUTA `target`. Autorizacao, validacao, auditoria e transacao
> ja' foram cuidadas pelo `runtime.execute_action` antes de chegar aqui.

## Passo 3 — Valide com a CLI

```bash
cd janus/backend
.venv/Scripts/python -m app.ontology.cli validate
```

Saida esperada:

```
→ Carregando definicoes...
  ✓ _markings.yaml (1 recurso)
  ...
  ✓ fornecedor.yaml (2 recursos)
  ...
→ Validando consistencia...
✓ Todas as validacoes passaram

Resumo:
  ObjectTypes: 6
  ActionTypes: 8
  MarkingSets: 1
```

Se algum YAML estiver mal formatado ou referenciar uma coluna inexistente
no model SQLAlchemy, a CLI lista o erro com path/linha.

## Passo 4 — Use via API REST

Suba o backend (`SmartJuno.bat` ou `uvicorn`) e:

```bash
# Lista os tipos — deve aparecer Fornecedor
curl -H "Authorization: Bearer $TOKEN" http://localhost:9050/api/v1/ontology/types

# Schema do Fornecedor
curl -H "Authorization: Bearer $TOKEN" http://localhost:9050/api/v1/ontology/types/Fornecedor

# Busca paginada
curl -H "Authorization: Bearer $TOKEN" 'http://localhost:9050/api/v1/ontology/Fornecedor?limit=10'

# Aprovar com dry-run (preview do diff antes de executar)
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  'http://localhost:9050/api/v1/ontology/Fornecedor/42/actions/aprovarFornecedor?dry_run=true' \
  -d '{"inputs": {"motivo": "auditoria 2026-Q2 aprovada"}}'

# Lineage (timeline de tudo que aconteceu com esse fornecedor)
curl -H "Authorization: Bearer $TOKEN" http://localhost:9050/api/v1/ontology/lineage/Fornecedor/42
```

## Passo 5 — Regenere os SDKs

```bash
.venv/Scripts/python -m app.ontology.cli generate-sdk --lang python --out sdk/python
.venv/Scripts/python -m app.ontology.cli generate-sdk --lang typescript --out janus/frontend/src/ontology
```

Agora voce tem clientes tipados em Python e TypeScript:

```python
from juno_ontology import Fornecedor

f = Fornecedor.get(42)
print(f.confiavel)   # True/False — computed property
result = f.aprovar_fornecedor(motivo="passou no compliance")
```

```typescript
import { getFornecedor, aprovarFornecedor } from "@/ontology";

const f = await getFornecedor(42);
const result = await aprovarFornecedor(42, { motivo: "ok" });
```

E o IA Coordinator automaticamente ganhou 4 tools novas:
`search_fornecedor`, `get_fornecedor_by_id`, `list_fornecedor`,
`propose_aprovarFornecedor`. Sem PR no `ai_coordinator.py`.

---

## Checklist do que voce ganha

- ✅ Schema versionado (YAML em git)
- ✅ API REST tipada e validada
- ✅ SDK Python + TS tipados gerados
- ✅ Tools auto-disponiveis no Coordinator
- ✅ Auditoria automatica (audit_logs) com diff before/after
- ✅ Permissioning (markings + roles + require_confirmation)
- ✅ Dry-run e preview no card de confirmacao da IA
- ✅ Lineage rastreavel
- ✅ Metricas Prometheus (latencia + counts)
- ✅ Zero codigo de glue entre camadas

## Erros comuns

**"backing.model: classe X nao existe"** — o dotted path no YAML aponta para
classe SQLAlchemy inexistente. Verifique o import em `app/models.py`.

**"property X referenciada em audit nao existe"** — voce listou em
`audit.fields_before/after` um campo que nao esta em `properties`. Adicione
ou remova da lista.

**"target_id obrigatorio"** ao chamar via IA — Actions sempre exigem o id
do objeto alvo via `target_id`, alem dos inputs.

**Action nao aparece para a IA** — confirme que listou o nome na chave
`actions: [...]` do ObjectType. So' Actions linkadas a um Object viram tools.

---

**Proximos passos:** veja [ONTOLOGY_DESIGN.md](./ONTOLOGY_DESIGN.md) secao 9
para o roadmap completo (Workshop, Branching, Pipeline declarativo).
