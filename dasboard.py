"""Data engine UNO — consolida demonstracoes do modelo Templates e gera payload do dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "janus" / "backend"
OUTPUT_DIR = ROOT / "uploads_piloto_juno"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.templates_financeiro import (  # noqa: E402
    DEFAULT_COMPETENCIA,
    DEFAULT_PATRIMONIAL,
    build_unified_payload,
    templates_available,
)


def main() -> None:
    if not templates_available():
        raise FileNotFoundError(f"Planilha modelo nao encontrada em {ROOT / 'Templates'}")

    payload = build_unified_payload(
        competencia=DEFAULT_COMPETENCIA,
        patrimonial=DEFAULT_PATRIMONIAL,
    )
    if payload is None:
        raise RuntimeError("Falha ao montar payload unificado a partir de Templates.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUTPUT_DIR / "dashboard_unificado_2025.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 90)
    print(f"   DATA ENGINE UNO — DASHBOARD UNIFICADO (ANO {DEFAULT_COMPETENCIA})")
    print("=" * 90)
    print(f"Fonte: {payload['meta']['fonte']}")
    print(f"Modelo KPI: {payload['meta']['modelo_kpi']}")
    print(f"Score Industrial: {payload['core']['score_industrial']}")
    print(f"Sintese: {payload['core']['sintese_ia']}")
    print("-" * 90)
    for kpi, dados in payload["kpis_unificados"].items():
        print(f"KPI: {kpi}")
        print(f"   Formula:  {dados['formula']}")
        print(f"   Valores:  {dados['valores']}")
        print(f"   Resultado: {dados['resultado']}")
        print("-" * 90)
    print(f"Payload JSON: {out_json}")


if __name__ == "__main__":
    main()
