"""
loader.py - carrega YAMLs de `definitions/` e popula o Registry.

Funcionalidade:
  - Parsing de arquivos YAML (multi-doc com `---`)
  - Validacao via Pydantic models do schema.py
  - Erros contextualizados (arquivo, linha quando disponivel)
  - Ordenacao: MarkingSets carregam primeiro (outros podem referenciar)
  - Idempotente: pode ser chamado varias vezes (registry.reset() entre chamadas)

Uso:
    from app.ontology import registry
    from app.ontology.loader import load_all

    load_all(registry)
    registry.validate_consistency()  # lista de erros (vazia se ok)
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .schema import (
    ActionTypeResource,
    MarkingSetResource,
    ObjectTypeResource,
    parse_resource,
)

logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


class OntologyLoadError(Exception):
    """Erro ao carregar/validar uma definicao ontologica."""

    def __init__(self, path: Path | str, detail: str, *, doc_index: int | None = None):
        self.path = path
        self.detail = detail
        self.doc_index = doc_index
        location = f"[{path}"
        if doc_index is not None:
            location += f" doc#{doc_index}"
        location += "]"
        super().__init__(f"{location} {detail}")


# =============================================================================
# Public API
# =============================================================================


def load_all(registry, definitions_dir: Path | None = None) -> dict[str, int]:
    """
    Carrega todos os YAMLs do diretorio no Registry.

    Ordem:
      1. _markings.yaml (MarkingSets primeiro)
      2. _types/*.yaml (tipos compartilhados, se houver)
      3. *.yaml restantes (ObjectTypes e ActionTypes)

    Args:
        registry: instancia Registry (geralmente o singleton).
        definitions_dir: override do diretorio padrao (util para testes).

    Returns:
        Dict {arquivo: numero_de_recursos_carregados}.

    Raises:
        OntologyLoadError: se algum YAML for invalido.
    """
    dir_ = definitions_dir or DEFINITIONS_DIR
    if not dir_.exists():
        raise OntologyLoadError(dir_, "diretorio de definitions nao existe")

    summary: dict[str, int] = {}

    # 1. Markings primeiro (prefixados com _)
    markings_file = dir_ / "_markings.yaml"
    if markings_file.exists():
        summary[markings_file.name] = load_file(registry, markings_file)

    # 2. Tipos compartilhados (futuramente; nao falha se vazio)
    types_dir = dir_ / "_types"
    if types_dir.exists():
        for f in sorted(types_dir.glob("*.yaml")):
            summary[f"_types/{f.name}"] = load_file(registry, f)

    # 3. Demais YAMLs (ObjectType e ActionType), em ordem alfabetica
    for f in sorted(dir_.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        summary[f.name] = load_file(registry, f)

    registry.mark_loaded()
    logger.info(
        "ontology: %d arquivos carregados (%d ObjectTypes, %d ActionTypes, %d MarkingSets)",
        len(summary),
        len(registry.list_object_types()),
        len(registry.list_action_types()),
        len(registry._marking_sets),  # noqa: SLF001 — leitura ok
    )
    return summary


def load_file(registry, path: Path) -> int:
    """
    Carrega um unico arquivo YAML (pode conter varios docs separados por ---).

    Returns:
        Numero de recursos carregados do arquivo.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise OntologyLoadError(path, f"falha ao ler arquivo: {e}") from e

    # safe_load_all retorna iterator de dicts (um por doc separado por ---)
    try:
        raw_docs = list(yaml.safe_load_all(text))
    except yaml.YAMLError as e:
        raise OntologyLoadError(path, f"YAML invalido: {e}") from e

    count = 0
    for i, raw in enumerate(raw_docs):
        if raw is None:  # doc vazio (ex: arquivo termina com ---\n)
            continue
        if not isinstance(raw, dict):
            raise OntologyLoadError(
                path,
                f"esperado um mapeamento YAML, recebido {type(raw).__name__}",
                doc_index=i,
            )
        try:
            resource = parse_resource(raw)
        except (ValueError, Exception) as e:
            # Pydantic ValidationError tambem cai aqui
            raise OntologyLoadError(path, str(e), doc_index=i) from e

        _register(registry, resource, path, i)
        count += 1

    return count


# =============================================================================
# Helpers privados
# =============================================================================


def _register(registry, resource, path: Path, doc_index: int) -> None:
    """Despacha o recurso para o metodo register_* apropriado."""
    try:
        if isinstance(resource, ObjectTypeResource):
            registry.register_object_type(resource)
        elif isinstance(resource, ActionTypeResource):
            registry.register_action_type(resource)
        elif isinstance(resource, MarkingSetResource):
            registry.register_marking_set(resource)
        else:
            raise OntologyLoadError(
                path,
                f"tipo de recurso desconhecido: {type(resource).__name__}",
                doc_index=doc_index,
            )
    except ValueError as e:
        # Conflito de nome (ja registrado)
        raise OntologyLoadError(path, str(e), doc_index=doc_index) from e
