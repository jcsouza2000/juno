# JUNO Ontology Engine — Design Document

> **Status:** Draft v1 · 2026-05-17
> **Autor:** Engenharia JUNO
> **Aprovação:** pendente
> **Implementação alvo:** v0.2.0 (4-6 semanas)
> **Inspiração:** Palantir Foundry Ontology · LinkML · dbt semantic layer

---

## 1. Por que Ontology

### 1.1 Problema atual

Hoje no JUNO o conhecimento de negócio está pulverizado em quatro lugares:

1. **`app/models.py`** — SQLAlchemy define o schema físico (tabelas, FKs).
2. **`app/services/`** — regras de negócio em Python (`get_cfo_margin_by_product`, etc.).
3. **`app/ai_coordinator.py`** — descrições de tools que a IA usa para consultar.
4. **Frontend** — labels, formatadores, fluxos de tela.

**Consequência:** quando "produto" muda (nova coluna, nova regra de margem, nova ação possível), é preciso editar 4-6 arquivos, em 4 linguagens, com 4 conceitos sutilmente diferentes da mesma entidade. Cada alteração quebra silenciosamente algum dos quatro.

### 1.2 O que Ontology resolve

Define **uma única descrição declarativa** (YAML) por entidade, e gera deterministicamente:

- Schemas Pydantic (entrada/saída de API)
- Schemas SQLAlchemy (opcional — pode espelhar models existentes)
- Tool descriptions para a IA (`get_*` e `do_*` automáticos)
- SDK Python e TypeScript com tipos completos
- Documentação OpenAPI/JSON-Schema
- Forms de UI auto-gerados (no futuro — Workshop)
- Política de permissioning por marking
- Auditoria automática (Action calls geram `audit_log` sem boilerplate)

A ontologia vira o **único contrato** entre dados, IA, código e UI.

### 1.3 Por que não Pydantic puro / SQLAlchemy puro / dbt

| Solução | Por que insuficiente |
|---|---|
| **Pydantic puro** | Não tem o conceito de Action (executa lógica). Não gera SDK TS. Sem permissioning embutido. |
| **SQLAlchemy declarativo** | Está acoplado ao SQL. Não modela Actions. IA precisaria parser. |
| **dbt semantic layer** | Excelente para BI analítico, mas não modela write-back/Actions transacionais. |
| **GraphQL schema** | Aproxima, mas não tem Actions tipadas com lógica nem permissioning declarativo. |
| **LinkML** | Modela bem; pode ser usado como base do nosso schema (decisão D-04 abaixo). |

---

## 2. Conceitos centrais

A ontologia tem **quatro primitivas**:

### 2.1 Object Type

Um tipo de objeto de negócio (`Produto`, `OrdemProducao`, `Cliente`).

Tem:
- **Properties** — campos tipados (string, number, date, enum, money).
- **Title property** — qual campo serve de "rótulo" humano (ex.: `name`).
- **Backing** — de onde os dados vêm: tabela SQL? API externa? Função?
- **Markings** — etiquetas de sensibilidade que se propagam (`PII`, `Confidencial`).
- **Primary key** — geralmente `id`, mas pode ser composto.

### 2.2 Link Type

Relacionamento entre Object Types (`Produto -> Empresa`, `OrdemProducao -> Produto`).

Tem:
- **Cardinality** — `one_to_one`, `one_to_many`, `many_to_many`.
- **Direction** — bidirecional por padrão; gera `produto.empresa` e `empresa.produtos`.
- **Backing** — FK SQL, tabela de junção, ou função custom.

### 2.3 Action Type

Operação que **muda estado** (`reagendarOrdem`, `aprovarPedido`, `atualizarPreco`).

Tem:
- **Inputs** — parâmetros tipados.
- **Effect** — função Python que executa.
- **Validation** — pré-condições (Pydantic + regras custom).
- **Authorization** — quais roles/markings podem chamar.
- **Audit** — auto-registra em `audit_logs` antes e depois.
- **Dry-run** — modo `validate-only` que retorna o que mudaria sem aplicar.

### 2.4 Function Type

Operação que **lê dado computado** (`calcularMargem`, `predizerDemanda`).

Diferente de Action: não muda estado. Pode ser cacheada. Pode ser chamada por outras Actions.

---

## 3. Arquitetura

### 3.1 Stack

```
┌─────────────────────────────────────────────────────────────┐
│  Definições YAML                                            │
│  app/ontology/definitions/*.yaml                            │
└──────────────┬──────────────────────────────────────────────┘
               │ parsing & validation (pydantic v2)
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Registry (in-memory, carregado no startup)                 │
│  app/ontology/registry.py                                   │
└──────┬──────────────┬──────────────┬────────────────────────┘
       │              │              │
       ▼              ▼              ▼
┌──────────┐  ┌─────────────┐  ┌──────────────────────┐
│  Runtime │  │  SDK Gen    │  │  AI Tool Generator   │
│  (CRUD,  │  │  Python+TS  │  │  (auto-build tools   │
│  Actions)│  │  artefatos  │  │  do Coordinator)     │
└────┬─────┘  └──────┬──────┘  └──────────┬───────────┘
     │               │                     │
     ▼               ▼                     ▼
  SQL/API       /sdk/python/         ai_coordinator.py
  backends      /sdk/typescript/     gera TOOLS auto
```

### 3.2 Estrutura de pastas

```
janus/backend/app/ontology/
├── __init__.py                # exporta Registry + helpers
├── README.md                  # overview do módulo
├── schema.py                  # Pydantic models que validam o YAML
├── loader.py                  # lê definitions/*.yaml e popula Registry
├── registry.py                # Registry singleton (ObjectType, LinkType, ActionType)
├── runtime.py                 # CRUD genérico + execução de Actions
├── permissions.py             # avaliação de markings + RBAC
├── audit.py                   # decorator que loga toda Action
├── sdk_gen/
│   ├── __init__.py
│   ├── python.py              # gera SDK Python (typed dataclasses + clients)
│   └── typescript.py          # gera SDK TS para o frontend
├── ai_tools.py                # converte Object/Action em tool spec do Coordinator
├── api.py                     # FastAPI router /api/v1/ontology/*
├── definitions/               # ← onde o usuário/dev declara a ontologia
│   ├── _types/                #   tipos primitivos compartilhados
│   │   └── money.yaml
│   ├── produto.yaml
│   ├── pedido_venda.yaml
│   ├── ordem_producao.yaml
│   ├── cliente.yaml
│   └── _markings.yaml         #   markings do tenant
└── tests/
    ├── test_loader.py
    ├── test_runtime.py
    └── test_actions.py
```

### 3.3 Como Object Types mapeiam aos models existentes

Decisão **D-01**: ontology **não substitui** SQLAlchemy. Ela é uma camada *acima*. Cada `ObjectType` declara um `backing.sqlalchemy_model` que aponta para a classe existente. O runtime usa o ORM para CRUD; a ontologia adiciona tipagem rica, Actions e permissioning.

Vantagem: nenhuma migration necessária. Coexiste com o código atual durante a transição.

Custo: precisamos manter mapping YAML ↔ SQLAlchemy. Validado no startup (fail-fast se YAML aponta para coluna inexistente).

---

## 4. Schema de uma definição (YAML)

Exemplo completo (Produto):

```yaml
# app/ontology/definitions/produto.yaml
apiVersion: ontology.juno.gravithy.com.br/v1
kind: ObjectType
metadata:
  name: Produto
  description: |
    Item comercializável da empresa — produto acabado, semi-acabado ou serviço.
  owner: catalog-team
  tags: [catalogo, comercial]

spec:
  backing:
    type: sqlalchemy
    model: app.models.Product
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
      marking: TenantScoped
    name:
      type: string
      required: true
      max_length: 255
    category:
      type: string
      enum_hint: [serviço, matéria-prima, produto-acabado, semi-acabado]
    standard_cost:
      type: money
      currency: BRL
      min: 0
    sale_price:
      type: money
      currency: BRL
      min: 0
    stock_quantity:
      type: integer
      min: 0
    min_stock:
      type: integer
      min: 0

  computed_properties:
    margem_unitaria:
      type: money
      formula: "sale_price - standard_cost"
      description: Margem nominal por unidade
    margem_percentual:
      type: percent
      formula: "(sale_price - standard_cost) / sale_price * 100 if sale_price > 0 else 0"
    abaixo_minimo:
      type: boolean
      formula: "stock_quantity < min_stock"

  links:
    empresa:
      target: Empresa
      cardinality: many_to_one
      backing:
        type: foreign_key
        column: company_id
      reverse_name: produtos
    ordens_producao:
      target: OrdemProducao
      cardinality: one_to_many
      backing:
        type: foreign_key
        target_column: product_id
    fornecedores:
      target: Fornecedor
      cardinality: many_to_many
      backing:
        type: junction_table
        table: supplier_products

  markings:
    inherit: [TenantScoped]   # company_id define tenant; só vê quem tem acesso à company

  actions:
    - atualizarPreco
    - desativarProduto

---
apiVersion: ontology.juno.gravithy.com.br/v1
kind: ActionType
metadata:
  name: atualizarPreco
  description: Atualiza o preço de venda de um produto com validação e auditoria.

spec:
  target: Produto

  inputs:
    novo_preco:
      type: money
      currency: BRL
      required: true
      min: 0
    motivo:
      type: string
      required: true
      max_length: 500
      description: Justificativa para o ajuste (obrigatório por compliance)

  validation:
    - rule: "novo_preco > standard_cost * 0.8"
      message: "Novo preço está muito abaixo do custo padrão (margem negativa > 20%)"
      severity: error
    - rule: "abs(novo_preco - sale_price) / sale_price < 0.5"
      message: "Variação > 50% do preço atual — confirme antes de aplicar"
      severity: warning

  authorization:
    roles: [admin, gerente_comercial]
    require_markings: []

  effect:
    handler: app.ontology.actions.product.update_price
    # async: false por padrão; transactional: true por padrão

  audit:
    fields_before: [sale_price]
    fields_after:  [sale_price]
    extra_context: [motivo]

  dry_run: supported
```

### 4.1 Tipos suportados

Primitivos: `string`, `integer`, `number`, `boolean`, `date`, `datetime`, `uuid`.

Compostos: `money` (com `currency`), `percent`, `enum`, `array<T>`, `ref<ObjectType>`.

Custom (via plugin): `cnpj`, `cpf`, `cep` — registrados em `app/ontology/types/`.

### 4.2 Computed properties

Expressões avaliadas no servidor com sandbox restritivo (sem `eval` cru — usar `asteval` ou similar). Decisão **D-02** abaixo.

### 4.3 Markings (permissioning)

Declaradas em `_markings.yaml`:

```yaml
apiVersion: ontology.juno.gravithy.com.br/v1
kind: MarkingSet
metadata:
  name: default

spec:
  markings:
    TenantScoped:
      description: Dado só visível dentro do tenant (company_id).
      enforcement: row_level
      predicate: "row.company_id in user.company_ids"
    PII:
      description: Informação pessoal identificável (LGPD art. 5).
      enforcement: column_level
      requires_role: [data_steward, admin]
    Confidencial-Comercial:
      description: Margem, preços negociados, contratos.
      requires_marking_grant: true  # usuário precisa de aprovação explícita
```

Toda query do runtime aplica filtros automaticamente.

---

## 5. Runtime: como uma chamada flui

### 5.1 Leitura (`GET /api/v1/ontology/Produto/123`)

```
1. Router recebe (object_type=Produto, id=123, user)
2. Registry.get_object_type("Produto") → ObjectTypeSpec
3. Permissions.can_read(user, spec) → checa markings
4. Runtime.fetch_by_id(spec, 123, user) → query no SQLAlchemy
   - WHERE company_id IN user.company_ids (de TenantScoped)
   - SELECT só de colunas que o user tem marking p/ ver
5. Computed properties são avaliadas
6. Response serializado via Pydantic gerado
```

### 5.2 Execução de Action (`POST /api/v1/ontology/Produto/123/actions/atualizarPreco`)

```
1. Router recebe (object_type, object_id, action_name, inputs, user)
2. Registry resolve ActionType
3. Permissions.can_execute(user, action) → roles + markings
4. Validation: pré-condições Pydantic + custom rules
5. Audit START → row em audit_logs com snapshot before
6. Effect handler é chamado em transação:
   - Pode ler outros objetos (com permissões do user)
   - Pode emitir eventos
   - Retorna estado after
7. Audit COMMIT → snapshot after + diff
8. Response: {success, before, after, audit_id}
```

### 5.3 Dry-run

`?dry_run=true` faz o passo 6 dentro de `with db.begin(): ... db.rollback()`. Retorna o que *teria* mudado.

---

## 6. SDK Generator

### 6.1 Python SDK

A partir de `produto.yaml`, geramos:

```python
# sdk/python/juno_ontology/produto.py (gerado automaticamente — não editar)
from typing import Optional
from datetime import datetime
from decimal import Decimal
from juno_ontology._base import ObjectClient, Money

class Produto(ObjectClient):
    """Item comercializável da empresa..."""

    id: int
    company_id: int
    name: str
    category: Optional[str]
    standard_cost: Money
    sale_price: Money
    stock_quantity: int

    @property
    def margem_unitaria(self) -> Money: ...
    @property
    def margem_percentual(self) -> float: ...
    @property
    def abaixo_minimo(self) -> bool: ...

    # Links (lazy)
    @property
    def empresa(self) -> "Empresa": ...
    @property
    def ordens_producao(self) -> list["OrdemProducao"]: ...

    # Actions (typed)
    def atualizar_preco(self, novo_preco: Money, motivo: str, dry_run: bool = False) -> "AtualizarPrecoResult": ...
```

Uso:

```python
from juno_ontology import client

prod = client.Produto.get(123)
print(prod.margem_percentual)

result = prod.atualizar_preco(
    novo_preco=Money(1250.00, "BRL"),
    motivo="reajuste de tabela 2026-Q2",
)
print(result.audit_id)
```

### 6.2 TypeScript SDK

Gerado para `janus/frontend/src/ontology/`. Hooks React inclusos:

```typescript
import { useProduto, useProdutoAction } from '@/ontology/produto';

const { data: prod } = useProduto(123);
const { mutate: atualizarPreco } = useProdutoAction('atualizarPreco');

atualizarPreco({ id: 123, novo_preco: 1250.00, motivo: '...' });
```

### 6.3 Quando o SDK é regenerado

Em build (CI) + manualmente (`make ontology-sdk`). Watcher em dev (`uvicorn --reload` dispara regen).

---

## 7. Integração com IA Coordinator

### 7.1 Tool generation automática

Hoje o `ai_coordinator.py` tem 7 tools hardcoded. Com Ontology:

```python
# app/ai_coordinator.py (depois)
from app.ontology import registry, ai_tools

TOOLS = ai_tools.build_tools_from_registry(registry)
# Gera automaticamente:
#   - search_<ObjectType>     → para cada Object Type
#   - get_<ObjectType>_by_id
#   - list_<ObjectType>_by_<link>
#   - execute_<ActionType>    → para cada Action
```

Resultado: quando você adiciona um YAML novo, a IA **automaticamente** ganha 4-5 tools sobre aquela entidade. Sem PR no Coordinator.

### 7.2 Write actions via IA — guard-rails

Decisão **D-03**: Actions chamadas pela IA exigem:

1. `confirmation_required: true` por default (usuário aprova no frontend antes do execute).
2. Markings do ator são as do **usuário humano** logado, não da IA.
3. `audit.actor_type = "ai_coordinator"` + `audit.confirmed_by = user_id`.
4. Rate limit específico por user para chamadas de Action via IA.

### 7.3 System prompt enriquecido

O prompt do Coordinator é regenerado a partir da ontologia:

```
Você é o Coordinator do JUNO.

Object Types disponíveis:
- Produto (catalogo): id, name, sale_price, margem_percentual, ...
- OrdemProducao (operacoes): id, status, atraso_dias, ...
- ...

Actions que você pode propor:
- atualizarPreco (Produto): requer role [admin, gerente_comercial]
- ...

Sempre busque dados reais via search_/get_ tools. Para Actions, proponha → usuário confirma → execute.
```

---

## 8. Decisões arquiteturais

| ID | Decisão | Alternativa rejeitada | Motivo |
|----|---------|----------------------|--------|
| **D-01** | Ontology é camada **acima** de SQLAlchemy (não substitui) | Reescrever models como ontology | Zero migration, coexistência durante transição |
| **D-02** | Computed properties usam `asteval` (sandbox restrito) | Eval cru ou DSL próprio | `asteval` é maduro, sandbox bom, sem inventar DSL |
| **D-03** | Actions via IA exigem confirmação humana por default | IA pode executar autonomamente | Risco. Mudamos default depois quando tivermos métricas. |
| **D-04** | Schema YAML inspirado em LinkML/CRD k8s, **não usa LinkML diretamente** | Adotar LinkML | LinkML é overkill. Nosso schema é específico para ontology operacional. |
| **D-05** | SDK gerado é **versionado** no repo (não build-time apenas) | Gerar só em build | IDE autocomplete funciona offline; PRs mostram impacto |
| **D-06** | YAMLs vão em `app/ontology/definitions/`, **não** em diretório separado | `ontology/` na raiz | Mantém ontology como parte do backend, deploy unificado |
| **D-07** | Frontend tipa via SDK TS gerado, não copia tipos manualmente | TypeScript handwritten | Single source of truth; quebra de compat aparece no build |
| **D-08** | Markings são **declarativos**, avaliados em runtime, **não** materializados | Materializar em colunas | Flexibilidade > performance neste estágio |

---

## 9. Roadmap de implementação (4-6 semanas)

### Semana 1 — Fundação
- [ ] Schema Pydantic para YAML (`app/ontology/schema.py`)
- [ ] Loader que valida e carrega definitions/ no startup
- [ ] Registry singleton com lookup por nome
- [ ] Testes: 3 YAMLs de exemplo carregam, errors claros para YAML mal formado
- [ ] CLI `juno ontology validate` (lint)

### Semana 2 — Runtime CRUD
- [ ] `Runtime.fetch_by_id`, `list`, `search` sobre SQLAlchemy
- [ ] Avaliação de computed properties (asteval)
- [ ] Markings básicos: TenantScoped funcional
- [ ] API REST `/api/v1/ontology/{type}/{id}` e `/list`
- [ ] Testes de integração com 3 ObjectTypes reais

### Semana 3 — Actions
- [ ] `ActionType` schema e validação
- [ ] Handler invocation (resolve dotted path, type-check inputs)
- [ ] Audit automático antes/depois
- [ ] Dry-run mode
- [ ] Implementar 3 Actions exemplo: `atualizarPreco`, `reagendarOrdem`, `aprovarPedido`

### Semana 4 — SDK
- [ ] Gerador Python (jinja templates)
- [ ] Gerador TypeScript
- [ ] Make targets `ontology-sdk-py`, `ontology-sdk-ts`
- [ ] CI roda gen + verifica que SDK no repo está atualizado (`git diff --exit-code`)

### Semana 5 — IA + Permissioning
- [ ] `ai_tools.build_tools_from_registry`
- [ ] Migrar Coordinator para tools auto-geradas (mantém retrocompat)
- [ ] Markings PII, Confidencial-Comercial
- [ ] Confirmation flow para Actions via IA (endpoint + UI)

### Semana 6 — Polish
- [ ] Lineage básico: cada Action registra `derived_from` em audit
- [ ] Docs/README + tutorial "criando seu primeiro ObjectType"
- [ ] Migration de 3-5 services existentes para usar runtime ontológico
- [ ] Métricas Prometheus (ontology calls por tipo, latência, taxa de erro)
- [ ] Feature flag para rollout gradual

---

## 10. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Performance: cada query passa por avaliação de markings | Média | Médio | Cache de policy compilada por user+type; benchmark contínuo |
| YAML vira "código sem testes" | Alta | Alto | `juno ontology validate` no pre-commit + CI; testes obrigatórios para cada Action |
| Drift entre YAML e models SQLAlchemy | Alta | Médio | Loader valida no startup; CI roda `ontology check-models` |
| Computed properties com expressão maliciosa | Baixa | Alto | `asteval` sandbox + lista branca de funções; revisão obrigatória de PR em `definitions/` |
| SDK gerado vira ruído em PRs | Média | Baixo | `*.generated.py` em `.gitattributes` (linguist-generated) |
| Adoção interna lenta (devs preferem ORM direto) | Alta | Alto | Migrar primeiro um service crítico end-to-end e medir tempo de mudança; treinamento + RFC obrigatório para novos endpoints |

---

## 11. Métricas de sucesso

Em 6 semanas, devemos conseguir medir:

- **Cobertura:** ≥ 60% dos endpoints novos passam pela ontologia (vs. 0% hoje).
- **Velocidade:** Adicionar novo Object Type leva < 1 hora (vs. ~1 dia hoje com 4-6 arquivos).
- **Auditoria:** 100% das Actions geram audit row com before/after (hoje ~30% via decorator manual).
- **IA:** Coordinator tem ≥ 25 tools auto-geradas (hoje 7 hardcoded).
- **SDK:** Frontend usa SDK TS gerado em ≥ 3 páginas (hoje 0).

---

## 12. Próximos passos pós-MVP

Depois deste design entregue:

1. **Pipeline declarativo (item 3 do roadmap Foundry)** — usa Object Types como inputs/outputs.
2. **AIP write-back (item 2)** — Actions são a primitiva natural.
3. **Workshop (item 7)** — form-builder lê schema da ontologia.
4. **Branching de dataset (item 5)** — versionamento por Object Type.

A ontologia é a infra-estrutura que viabiliza todos esses passos. Sem ela, cada um vira retrabalho.

---

## Anexos

### A. Comparativo Foundry vs JUNO Ontology

| Conceito Foundry | Equivalente JUNO | Status |
|---|---|---|
| Object Type | ObjectType (YAML) | planejado v1 |
| Link Type | Link (dentro de ObjectType) | planejado v1 |
| Action Type | ActionType (YAML) | planejado v1 |
| Function | Function (Python registrada) | planejado v1 |
| Marking | Marking (YAML) | planejado v1 |
| Branch | — | item 5 do roadmap (não nesta entrega) |
| Time-travel | — | item 5 do roadmap |
| Workshop | — | item 7 do roadmap |

### B. Exemplos de uso (uma vez implementado)

```bash
# Listar Object Types
$ juno ontology list
ObjectType: Produto (10 actions, 4 links)
ObjectType: PedidoVenda (3 actions, 3 links)
ObjectType: OrdemProducao (5 actions, 4 links)

# Validar YAMLs
$ juno ontology validate
✓ produto.yaml
✓ pedido_venda.yaml
✗ ordem_producao.yaml: property 'foo' references column 'foo' not present in ProductionOrder

# Regenerar SDK
$ make ontology-sdk
Generated 14 Python types in sdk/python/
Generated 14 TS types in janus/frontend/src/ontology/

# Aplicar uma Action via curl
$ curl -X POST http://localhost:9050/api/v1/ontology/Produto/123/actions/atualizarPreco \
  -H "Authorization: Bearer ..." \
  -d '{"novo_preco": 1250.00, "motivo": "reajuste 2026-Q2"}'
```

### C. Referências

- Palantir Foundry — *Ontology overview*, public docs.
- LinkML — *https://linkml.io/* (schema language para data).
- dbt Semantic Layer — *https://docs.getdbt.com/docs/build/semantic-models*.
- Pydantic v2 — validação de schemas YAML.
- asteval — sandbox seguro para expressions Python.
- Kubernetes CRDs — inspiração para apiVersion/kind/metadata/spec.

---

**Fim do design.** Próximo passo: aprovar este doc, depois iniciar Semana 1 do roadmap.
