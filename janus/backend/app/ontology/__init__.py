"""
JUNO Ontology Engine
====================

Camada declarativa que define Object Types, Link Types, Action Types e Functions
em YAML, e gera deterministicamente schemas, SDK, tools de IA e permissioning.

Inspirado em Palantir Foundry Ontology.

Status: scaffolding (v0.2.0-dev). Ver `docs/ONTOLOGY_DESIGN.md`.

Uso típico (uma vez implementado):

    from app.ontology import registry, runtime, Registry

    # Carrega definitions/ no startup
    Registry.load_all()

    # Lê um objeto
    prod = runtime.fetch_by_id("Produto", 123, user=current_user)

    # Executa uma action
    result = runtime.execute_action(
        "atualizarPreco",
        target_id=123,
        inputs={"novo_preco": 1250.00, "motivo": "reajuste"},
        user=current_user,
    )
"""

from .registry import Registry, registry

__all__ = ["Registry", "registry"]
__version__ = "0.1.0-dev"
