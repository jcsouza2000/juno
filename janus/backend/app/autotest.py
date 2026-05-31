"""
Auto Teste — JUNO Industrial Diagnostic
Executa todos os componentes internamente e emite resultados via SSE.
"""

import json
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import dashboards, data_quality, insights, models
from . import demo as demo_module
from . import financials as fin_module
from .ai_coordinator import _run_tool


def _run(test_id: str, name: str, category: str, fn) -> dict:
    t0 = time.perf_counter()
    try:
        result = fn()
        duration = int((time.perf_counter() - t0) * 1000)
        if isinstance(result, list):
            detail = f"{len(result)} registro(s)"
        elif isinstance(result, dict):
            keys = list(result.keys())[:4]
            detail = f"Chaves: {', '.join(str(k) for k in keys)}"
        elif isinstance(result, (int, float)):
            detail = str(result)
        else:
            detail = "OK"
        return {
            "id": test_id,
            "name": name,
            "category": category,
            "status": "pass",
            "duration_ms": duration,
            "detail": detail,
        }
    except Exception as exc:
        duration = int((time.perf_counter() - t0) * 1000)
        return {
            "id": test_id,
            "name": name,
            "category": category,
            "status": "fail",
            "duration_ms": duration,
            "detail": str(exc)[:300],
        }


def run_all(db: Session):
    """
    Generator — emite um dict JSON por teste, depois um evento __summary__.
    Cada evento deve ser serializado para SSE pelo chamador.
    """
    results: list[dict] = []

    def emit(test_id, name, category, fn):
        r = _run(test_id, name, category, fn)
        results.append(r)
        return json.dumps(r)

    # ── Sistema ────────────────────────────────────────────────────────────
    yield emit(
        "sys_db",
        "Conexão com banco de dados",
        "Sistema",
        lambda: db.execute(text("SELECT 1")).fetchone(),
    )
    yield emit(
        "sys_companies", "Empresas cadastradas", "Sistema", lambda: db.query(models.Company).count()
    )
    yield emit(
        "sys_tables",
        "Tabelas ORM mapeadas",
        "Sistema",
        lambda: list(models.Base.metadata.tables.keys()),
    )
    yield emit(
        "sys_products", "Produtos cadastrados", "Sistema", lambda: db.query(models.Product).count()
    )
    yield emit(
        "sys_orders",
        "Pedidos de venda totais",
        "Sistema",
        lambda: db.query(models.SalesOrder).count(),
    )

    # ── Minha Empresa (base primaria, id=1) ────────────────────────────────
    yield emit("a_ceo", "CEO KPIs", "Minha Empresa", lambda: dashboards.get_ceo_kpis(db, 1))
    yield emit(
        "a_cfo",
        "Margens por produto",
        "Minha Empresa",
        lambda: dashboards.get_cfo_margin_by_product(db, 1),
    )
    yield emit(
        "a_coo",
        "Ordens atrasadas",
        "Minha Empresa",
        lambda: dashboards.get_coo_delayed_orders(db, 1),
    )
    yield emit(
        "a_insights",
        "Insights operacionais",
        "Minha Empresa",
        lambda: insights.generate_insights(1, db),
    )
    yield emit(
        "a_score", "Score JUNO", "Minha Empresa", lambda: insights.calculate_juno_score(1, db)
    )
    yield emit(
        "a_dq",
        "Validacao de qualidade",
        "Minha Empresa",
        lambda: data_quality.get_full_validation_report(1, db),
    )
    yield emit(
        "a_demo", "Resumo executivo", "Minha Empresa", lambda: demo_module.get_demo_summary(1, db)
    )

    # ── Base secundaria (id=2) — mantida para compat de seed; rotulos genericos
    yield emit(
        "b_ceo", "CEO KPIs (base 2)", "Minha Empresa", lambda: dashboards.get_ceo_kpis(db, 2)
    )
    yield emit(
        "b_cfo",
        "Margens por produto (base 2)",
        "Minha Empresa",
        lambda: dashboards.get_cfo_margin_by_product(db, 2),
    )
    yield emit(
        "b_coo",
        "Ordens atrasadas (base 2)",
        "Minha Empresa",
        lambda: dashboards.get_coo_delayed_orders(db, 2),
    )
    yield emit(
        "b_insights",
        "Insights operacionais (base 2)",
        "Minha Empresa",
        lambda: insights.generate_insights(2, db),
    )
    yield emit(
        "b_score",
        "Score JUNO (base 2)",
        "Minha Empresa",
        lambda: insights.calculate_juno_score(2, db),
    )
    yield emit(
        "b_dq",
        "Validacao de qualidade (base 2)",
        "Minha Empresa",
        lambda: data_quality.get_full_validation_report(2, db),
    )
    yield emit(
        "b_demo",
        "Resumo executivo (base 2)",
        "Minha Empresa",
        lambda: demo_module.get_demo_summary(2, db),
    )

    # ── IA Tools (coordinator) ─────────────────────────────────────────────
    ai_tools = [
        ("get_company_overview", "Tool: get_company_overview"),
        ("get_margin_analysis", "Tool: get_margin_analysis"),
        ("get_production_delays", "Tool: get_production_delays"),
        ("get_insights", "Tool: get_insights"),
        ("validate_data_quality", "Tool: validate_data_quality"),
        ("get_full_diagnostic", "Tool: get_full_diagnostic"),
        ("get_financial_statements", "Tool: get_financial_statements"),
    ]
    for tool_name, label in ai_tools:
        yield emit(
            f"ai_{tool_name}",
            label,
            "IA Coordinator",
            lambda n=tool_name: _run_tool(n, {"company_id": 1}, db),
        )

    # ── Demonstrações Financeiras ──────────────────────────────────────────
    yield emit(
        "fin_a",
        "Resumo financeiro",
        "Demonstrações",
        lambda: fin_module.get_financial_summary(1, db),
    )
    yield emit(
        "fin_b",
        "Resumo financeiro (base 2)",
        "Demonstrações",
        lambda: fin_module.get_financial_summary(2, db),
    )
    yield emit(
        "fin_ha",
        "Histórico de uploads",
        "Demonstrações",
        lambda: fin_module.get_upload_history(1, db),
    )
    yield emit(
        "fin_hb",
        "Histórico de uploads (base 2)",
        "Demonstrações",
        lambda: fin_module.get_upload_history(2, db),
    )

    # ── Sumário final ──────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = total - passed
    avg_ms = int(sum(r["duration_ms"] for r in results) / total) if total else 0
    total_ms = sum(r["duration_ms"] for r in results)

    yield json.dumps(
        {
            "id": "__summary__",
            "status": "complete",
            "total": total,
            "passed": passed,
            "failed": failed,
            "avg_duration_ms": avg_ms,
            "total_duration_ms": total_ms,
            "failures": [r for r in results if r["status"] == "fail"],
        }
    )
