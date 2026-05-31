# app/ontology — JUNO Ontology Engine

> **Status:** scaffolding (v0.2.0-dev). Ver [`docs/ONTOLOGY_DESIGN.md`](../../../docs/ONTOLOGY_DESIGN.md) para arquitetura completa.

## O que vai aqui

Camada declarativa que substitui a duplicação atual entre `models.py`, `services/`,
`ai_coordinator.py` e tipos do frontend. Uma definição YAML por entidade gera:

- Schemas Pydantic
- SDK Python e TypeScript
- Tools auto-geradas para a IA
- Permissioning por marking
- Auditoria automática de Actions

## Estrutura

```
ontology/
├── __init__.py           # exporta Registry
├── schema.py             # Pydantic models que validam YAML
├── loader.py             # parse + carrega definitions/
├── registry.py           # singleton in-memory
├── runtime.py            # CRUD + execução de Actions
├── permissions.py        # markings + RBAC
├── audit.py              # decorator de auditoria
├── api.py                # FastAPI router
├── ai_tools.py           # gera tool specs para o Coordinator
├── sdk_gen/              # geradores de SDK Py/TS
└── definitions/          # ← YAMLs declarativos
    ├── produto.yaml
    ├── pedido_venda.yaml
    ├── ordem_producao.yaml
    └── _markings.yaml
```

## Como começar (depois do MVP)

1. **Criar um Object Type novo:** copiar um YAML de `definitions/` e adaptar.
2. **Adicionar Action:** declarar `ActionType` + implementar handler em `app/ontology/actions/<dominio>.py`.
3. **Regenerar SDK:** `make ontology-sdk`.
4. **Validar:** `juno ontology validate`.

## Roadmap

Ver design doc, seção 9. Resumo:
- Sem 1: schema + loader
- Sem 2: runtime CRUD + markings básico
- Sem 3: Actions + audit
- Sem 4: SDK gen
- Sem 5: IA tools + permissioning avançado
- Sem 6: lineage + métricas + migração de services

## Testes

```bash
cd janus/backend
.venv/Scripts/python -m pytest app/ontology/tests/ -v
```

## Comandos CLI (planejados)

```
juno ontology list                          # lista Object Types
juno ontology validate                      # lint dos YAMLs
juno ontology describe Produto              # detalhe de um tipo
juno ontology generate-sdk --lang python    # regen SDK
juno ontology check-models                  # valida que YAML ↔ SQLAlchemy batem
```
