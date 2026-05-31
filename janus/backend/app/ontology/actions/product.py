"""Handlers para Actions sobre Produto."""

from __future__ import annotations


def update_price(target, inputs, *, db, user, cursor):
    """
    atualizarPreco: troca sale_price.
    Quando `aplicar_em_pedidos_abertos=True`, registra warning para job
    assincrono cuidar dos pedidos vinculados (nao bloqueia a action).
    """
    novo_preco = inputs["novo_preco"]
    target.sale_price = float(novo_preco)
    cursor.add_context("novo_preco", novo_preco)
    cursor.add_context("motivo", inputs["motivo"])

    if inputs.get("aplicar_em_pedidos_abertos"):
        cursor.add_warning(
            "aplicar_em_pedidos_abertos=true ainda nao implementado — pedidos abertos "
            "manterao o preco antigo. Implementacao na Sem4."
        )


def deactivate(target, inputs, *, db, user, cursor):
    """
    desativarProduto: soft delete por convencao —
    zera sale_price e stock_quantity (ate termos coluna 'status' no model).
    """
    target.sale_price = 0.0
    target.stock_quantity = 0
    cursor.add_context("motivo", inputs["motivo"])
    if "data_efetiva" in inputs:
        cursor.add_context("data_efetiva", inputs["data_efetiva"])
