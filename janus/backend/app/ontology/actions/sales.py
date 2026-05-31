"""Handlers para Actions sobre PedidoVenda."""

from __future__ import annotations


def approve(target, inputs, *, db, user, cursor):
    """
    aprovarPedido: nao ha coluna 'status' em SalesOrder, entao apenas
    registra o ato em audit_logs via cursor (que ja captura inputs).
    Quando a migration adicionar 'status', basta mudar aqui.
    """
    if "observacao" in inputs:
        cursor.add_context("observacao", inputs["observacao"])
    cursor.add_warning(
        "Workflow de status de PedidoVenda ainda nao migrado. Aprovacao "
        "registrada em audit_logs apenas. Migration prevista Sem4."
    )


def apply_discount(target, inputs, *, db, user, cursor):
    """aplicarDesconto: ajusta discount e recalcula total."""
    valor = float(inputs["valor_desconto"])
    target.discount = valor
    target.total = float(target.revenue or 0) - valor
    cursor.add_context("motivo", inputs["motivo"])
    cursor.add_context("valor_desconto", valor)
