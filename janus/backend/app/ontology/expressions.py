"""
expressions.py - avaliacao segura de expressoes Python para computed properties
e validation rules.

Usa asteval — interpretador restrito que nao executa import, exec, eval, nem
acessa builtins perigosos. Apenas operacoes matematicas, condicionais e
funcoes da whitelist.

Filosofia: as expressoes em YAML sao codigo de negocio escrito por analistas.
Devem ser legiveis e seguras por construcao. Nada de `__import__` ou `os.system`.

Whitelist atual:
  - aritmetica e comparacoes
  - if/else
  - abs, min, max, round, len
  - bool, int, float, str (conversao)
  - Numeros: int, float
  - None, True, False
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

try:
    from asteval import Interpreter

    _ASTEVAL_AVAILABLE = True
except ImportError:
    _ASTEVAL_AVAILABLE = False
    Interpreter = None


class ExpressionError(Exception):
    """Erro na avaliacao de uma expressao da ontologia."""

    def __init__(self, formula: str, detail: str):
        self.formula = formula
        self.detail = detail
        super().__init__(f"[expr: {formula!r}] {detail}")


# Cache de interpretadores por thread (asteval nao e' thread-safe; aqui criamos
# um por chamada para simplicidade — overhead aceitavel em runtime de read).
def _make_interpreter():
    if not _ASTEVAL_AVAILABLE:
        raise RuntimeError("asteval nao esta instalado. Adicione `asteval==1.0.5` ao requirements.")
    aeval = Interpreter(
        # Sem builtins perigosos
        use_numpy=False,
        minimal=False,
        no_print=True,
        no_if=False,
        no_for=True,  # for desabilitado: expressoes nao iteram
        no_while=True,
        no_try=True,
        no_functiondef=True,
        no_ifexp=False,  # ternario `x if cond else y` permitido
        no_listcomp=True,
        no_augassign=True,
        no_assert=True,
        no_delete=True,
        no_raise=True,
        no_print_func=True,
    )
    # Helpers seguros
    aeval.symtable["abs"] = abs
    aeval.symtable["min"] = min
    aeval.symtable["max"] = max
    aeval.symtable["round"] = round
    aeval.symtable["len"] = len
    return aeval


def evaluate(formula: str, context: dict[str, Any]) -> Any:
    """
    Avalia `formula` com `context` como namespace.

    Args:
        formula: expressao Python valida (sintaxe restrita)
        context: dict {var_name: value} — properties do objeto, inputs da action

    Returns:
        Resultado da avaliacao.

    Raises:
        ExpressionError: se asteval reportar erro ou expressao referir nome nao-bind.
    """
    aeval = _make_interpreter()

    # Injeta contexto. asteval ja serializa para sua simbolica.
    for k, v in context.items():
        aeval.symtable[k] = v

    # `now` e' frequentemente util em formulas de OrdemProducao (atrasada, etc.)
    aeval.symtable.setdefault("now", _dt.datetime.utcnow())

    result = aeval(formula)

    if aeval.error:
        # asteval acumula erros em aeval.error_msg
        msg = "; ".join(str(err.get_error()) for err in aeval.error)
        raise ExpressionError(formula, msg)

    return result


def evaluate_bool(formula: str, context: dict[str, Any]) -> bool:
    """Avalia e converte para bool. Usado em validation rules."""
    result = evaluate(formula, context)
    return bool(result)


def compute_properties(
    computed_specs: dict[str, Any],
    row_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Avalia todas as computed_properties de um ObjectType.

    Args:
        computed_specs: dict {name: ComputedPropertySpec}
        row_data: dict com properties ja carregadas da linha SQL

    Returns:
        dict {nome_computed: valor} — falhas individuais retornam None com warning.
    """
    out: dict[str, Any] = {}
    for name, spec in computed_specs.items():
        try:
            out[name] = evaluate(spec.formula, dict(row_data))
        except ExpressionError:
            # Nao quebra a leitura do objeto inteiro por uma formula com bug.
            # Em prod isso poderia logar com structlog + emitir metrica.
            out[name] = None
    return out
