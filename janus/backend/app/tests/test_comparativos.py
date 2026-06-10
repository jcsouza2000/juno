"""Testes dos comparativos historicos (Fase A)."""

from app import templates_financeiro as tf


def test_build_comparativos_section_has_qoq_and_yoy():
    report = tf.build_demonstracoes_relatorio()
    assert report is not None
    comparativos = next(s for s in report["secoes"] if s["id"] == "comparativos")
    linhas = comparativos["linhas"]
    assert len(linhas) > 0
    tipos = {row["tipo"] for row in linhas}
    assert "QoQ" in tipos
    assert "YoY" in tipos
    first = linhas[0]
    assert "indicador_key" in first
    assert "variacao_pct" in first


def test_report_lines_have_conta_key():
    report = tf.build_demonstracoes_relatorio()
    assert report is not None
    dre = next(s for s in report["secoes"] if s["id"] == "dre")
    assert all("conta_key" in line for line in dre["linhas"])
