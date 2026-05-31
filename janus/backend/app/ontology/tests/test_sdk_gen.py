"""
test_sdk_gen.py - testes dos geradores de SDK Python e TypeScript.

Garante que:
  - Geracao Python produz arquivos com sintaxe Python valida (ast.parse)
  - Cada ObjectType vira um arquivo + classe
  - Properties, computed, links e actions aparecem nos arquivos
  - Geracao TS produz strings sem palavras-chave proibidas (process, require)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.ontology.sdk_gen.python import (
    _py_type_for_required,
    _snake_case,
    generate_python_sdk,
)
from app.ontology.sdk_gen.typescript import (
    _camel_case,
    _pascal_case,
    _ts_type,
    generate_typescript_sdk,
)

# =============================================================================
# Helpers
# =============================================================================


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# =============================================================================
# Type mapping
# =============================================================================


class TestTypeMapping:
    def test_python_required_strips_optional(self):
        assert _py_type_for_required("string", True) == "str"
        assert _py_type_for_required("string", False) == "str | None"
        assert _py_type_for_required("integer", True) == "int"
        assert _py_type_for_required("money", False) == "float | None"

    def test_python_unknown_falls_to_any(self):
        assert _py_type_for_required("blah", True) == "Any"

    def test_ts_basic(self):
        assert _ts_type("string") == "string"
        assert _ts_type("money") == "number"
        assert _ts_type("boolean") == "boolean"
        assert _ts_type("unknownxxx") == "unknown"

    def test_snake_case(self):
        assert _snake_case("Produto") == "produto"
        assert _snake_case("PedidoVenda") == "pedido_venda"
        assert _snake_case("OrdemProducao") == "ordem_producao"

    def test_camel_pascal(self):
        assert _camel_case("Produto") == "produto"
        assert _camel_case("pedido_venda") == "pedidoVenda"
        assert _pascal_case("atualizarPreco") == "AtualizarPreco"
        assert _pascal_case("aplicar_desconto") == "AplicarDesconto"


# =============================================================================
# Python SDK
# =============================================================================


class TestPythonSDK:
    @pytest.fixture
    def py_sdk(self, loaded_registry, tmp_path) -> dict[str, Path]:
        return generate_python_sdk(loaded_registry, tmp_path)

    def test_files_generated(self, py_sdk):
        names = set(py_sdk.keys())
        assert "_base.py" in names
        assert "__init__.py" in names
        assert "produto.py" in names
        assert "pedido_venda.py" in names
        assert "ordem_producao.py" in names
        assert "empresa.py" in names
        assert "cliente.py" in names

    def test_all_files_parse_as_python(self, py_sdk):
        for name, path in py_sdk.items():
            try:
                ast.parse(_read(path))
            except SyntaxError as e:
                pytest.fail(f"{name} nao e' Python valido: {e}")

    def test_produto_has_class_and_attrs(self, py_sdk):
        src = _read(py_sdk["produto.py"])
        assert "class Produto(ObjectClient)" in src
        assert 'OBJECT_TYPE: ClassVar[str] = "Produto"' in src
        # Properties principais
        assert "id: int" in src
        assert "company_id: int" in src
        assert "name: str" in src
        # Computed properties como anotacoes
        assert "margem_unitaria" in src
        assert "margem_percentual" in src
        # Actions como metodos
        assert "def atualizar_preco" in src
        assert "def desativar_produto" in src

    def test_produto_action_signature(self, py_sdk):
        src = _read(py_sdk["produto.py"])
        # atualizar_preco deve ter novo_preco e motivo como params
        assert "novo_preco: float" in src
        assert "motivo: str" in src
        # E os defaults de actor
        assert 'actor_type: str = "user"' in src
        assert "dry_run: bool = False" in src

    def test_links_methods_generated(self, py_sdk):
        src = _read(py_sdk["produto.py"])
        assert "def get_empresa" in src
        assert "def get_ordens_producao" in src
        assert "def get_pedidos_venda" in src

    def test_init_exports_all_classes(self, py_sdk):
        src = _read(py_sdk["__init__.py"])
        for cls in ("Produto", "PedidoVenda", "OrdemProducao", "Empresa", "Cliente"):
            assert f'"{cls}"' in src
            assert (
                f"from .{cls.lower().replace('producao', '_producao').replace('venda', '_venda')}"
                in src
                or f"import {cls}" in src
            )

    def test_base_has_http_client(self, py_sdk):
        src = _read(py_sdk["_base.py"])
        assert "class HTTPClient" in src
        assert "class ObjectClient" in src
        assert "class ActionResult" in src
        assert "class Money" in src
        assert "class PermissionDenied" in src


# =============================================================================
# TypeScript SDK
# =============================================================================


class TestTypeScriptSDK:
    @pytest.fixture
    def ts_sdk(self, loaded_registry, tmp_path) -> dict[str, Path]:
        return generate_typescript_sdk(loaded_registry, tmp_path)

    def test_files_generated(self, ts_sdk):
        names = set(ts_sdk.keys())
        assert "_base.ts" in names
        assert "index.ts" in names
        assert "produto.ts" in names
        assert "pedido_venda.ts" in names

    def test_no_node_globals_referenced(self, ts_sdk):
        """Nao deve referenciar `process.` direto nem `require(` — usamos globalThis."""
        for name, path in ts_sdk.items():
            src = _read(path)
            assert "require(" not in src, f"{name} contem require()"
            # process e' permitido via globalThis cast
            for line in src.splitlines():
                if "process" in line and "globalThis" not in line and "process?" not in line:
                    if not line.strip().startswith(("//", "*", "/*")):
                        pytest.fail(f"{name}: referencia direta a `process`: {line}")

    def test_produto_interface(self, ts_sdk):
        src = _read(ts_sdk["produto.ts"])
        assert "export interface Produto" in src
        assert "id: number" in src
        assert "company_id: number" in src
        assert "name: string" in src
        # Computed properties (opcionais — `?:`)
        assert "margem_unitaria?: number" in src
        assert "abaixo_minimo?: boolean" in src

    def test_produto_action_iface(self, ts_sdk):
        src = _read(ts_sdk["produto.ts"])
        assert "export interface AtualizarPrecoInputs" in src
        assert "novo_preco: number" in src
        assert "motivo: string" in src
        assert "export function atualizarPreco" in src

    def test_index_reexports(self, ts_sdk):
        src = _read(ts_sdk["index.ts"])
        assert 'export * from "./_base"' in src
        assert 'export * from "./produto"' in src
        assert 'export * from "./empresa"' in src

    def test_base_has_http_client(self, ts_sdk):
        src = _read(ts_sdk["_base.ts"])
        assert "export class OntologyClient" in src
        assert "export interface ActionResult" in src
        assert "export interface Money" in src
        assert "ValidationFailed" in src


# =============================================================================
# Importing the generated Python SDK works
# =============================================================================


def test_generated_python_sdk_imports(loaded_registry, tmp_path, monkeypatch):
    """
    Gera o SDK Python e verifica que ele importa sem erros num subprocess.
    Mais robusto que importar via importlib (que pode poluir sys.modules).
    """
    import subprocess
    import sys

    generate_python_sdk(loaded_registry, tmp_path)
    pkg_dir = tmp_path / "juno_ontology"
    assert pkg_dir.exists()

    # Subprocess Python que importa o pacote gerado
    code = (
        f"import sys; sys.path.insert(0, {str(tmp_path)!r});"
        "from juno_ontology import Produto, PedidoVenda, OrdemProducao, Empresa, Cliente;"
        "from juno_ontology import HTTPClient, ActionResult, Money;"
        "assert Produto.OBJECT_TYPE == 'Produto';"
        "assert PedidoVenda.OBJECT_TYPE == 'PedidoVenda';"
        "print('OK')"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, f"stderr:\n{r.stderr}\nstdout:\n{r.stdout}"
    assert "OK" in r.stdout
