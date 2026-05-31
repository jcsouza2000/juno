"""Handlers para Actions sobre OrdemProducao."""

from __future__ import annotations

from datetime import datetime


def reschedule(target, inputs, *, db, user, cursor):
    """reagendarOrdem: move planned_date."""
    nova_data = inputs["nova_data_planejada"]
    if isinstance(nova_data, str):
        nova_data = datetime.fromisoformat(nova_data.replace("Z", "+00:00"))
        if nova_data.tzinfo is not None:
            nova_data = nova_data.replace(tzinfo=None)
    target.planned_date = nova_data
    cursor.add_context("motivo", inputs["motivo"])
    if inputs.get("notificar_cliente"):
        cursor.add_warning("notificar_cliente=true — integracao de notificacao pendente (Sem6).")


def cancel(target, inputs, *, db, user, cursor):
    """cancelarOrdem: muda status para 'cancelled'."""
    target.status = "cancelled"
    cursor.add_context("motivo", inputs["motivo"])
    if inputs.get("reverter_estoque"):
        cursor.add_warning(
            "reverter_estoque=true — reversao de estoque sera implementada na Sem4 "
            "junto com pipeline de eventos."
        )


def complete(target, inputs, *, db, user, cursor):
    """registrarConclusao: marca status=completed e grava actuals."""
    actual_date = inputs["actual_date"]
    if isinstance(actual_date, str):
        actual_date = datetime.fromisoformat(actual_date.replace("Z", "+00:00"))
        if actual_date.tzinfo is not None:
            actual_date = actual_date.replace(tzinfo=None)
    target.actual_qty = int(inputs["actual_qty"])
    target.actual_cost = float(inputs["actual_cost"])
    target.actual_date = actual_date
    target.status = "completed"
