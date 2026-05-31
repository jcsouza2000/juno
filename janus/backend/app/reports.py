import re
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import dashboards, insights
from .score_v2 import get_score_calculator

# ── Brand Palette ────────────────────────────────────────────────────────────
JUNO_BLUE = colors.HexColor("#0A2342")
JUNO_GOLD = colors.HexColor("#C9A959")
JUNO_LIGHT = colors.HexColor("#F0F4F8")
JUNO_RED = colors.HexColor("#C0392B")
JUNO_GREEN = colors.HexColor("#1A7A4A")
JUNO_YELLOW = colors.HexColor("#E6A817")
JUNO_GRAY = colors.HexColor("#6B7280")
JUNO_WHITE = colors.white


# ── Helpers ───────────────────────────────────────────────────────────────────
def _score_color(score):
    if score >= 85:
        return JUNO_GREEN
    if score >= 70:
        return JUNO_GOLD
    if score >= 50:
        return JUNO_YELLOW
    return JUNO_RED


def _score_label(score):
    if score >= 85:
        return "EXCELENTE"
    if score >= 70:
        return "BOM"
    if score >= 50:
        return "ATENÇÃO"
    return "CRÍTICO"


def _executive_narrative(score, company_name, total_risks, delays, neg_products):
    if score >= 85:
        return (
            f"A análise do Juno indica que {company_name} apresenta excelente saúde "
            f"operacional (Score {score}/100). Os processos industriais estão alinhados "
            f"com as metas de eficiência e rentabilidade."
        )
    if score >= 70:
        return (
            f"A análise do Juno identificou que {company_name} apresenta boa saúde "
            f"operacional (Score {score}/100), porém com {total_risks} risco(s) que "
            f"merecem atenção para manutenção da margem e competitividade."
        )
    if score >= 50:
        return (
            f"A análise do Juno identificou riscos relevantes na operação de "
            f"{company_name} (Score {score}/100), com impacto direto na margem e "
            f"eficiência produtiva. Foram detectados {neg_products} produto(s) com "
            f"margem comprometida e {delays} ordem(ns) em atraso."
        )
    return (
        f"A análise do Juno aponta situação CRÍTICA na operação de {company_name} "
        f"(Score {score}/100). Ação imediata é necessária para reverter perdas "
        f"financeiras e operacionais identificadas. Cada semana de inação amplia "
        f"o impacto estimado."
    )


def _delays_from_insights(company_insights):
    for i in company_insights:
        if i["type"] == "delay_risk":
            m = re.match(r"(\d+)", i["message"])
            if m:
                return int(m.group(1))
    return 0


# ── Main Generator ────────────────────────────────────────────────────────────
def generate_pdf_report(company_name, company_id, db):
    buffer = BytesIO()

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(JUNO_GRAY)
        footer = (
            f"{company_name}  |  Juno Diagnóstico Industrial v0.2.1  |  "
            f"{date.today().strftime('%d/%m/%Y')}  |  "
            f"Pág. {canvas.getPageNumber()}"
        )
        canvas.drawCentredString(A4[0] / 2, 0.45 * inch, footer)
        # gold line above footer
        canvas.setStrokeColor(JUNO_GOLD)
        canvas.setLineWidth(0.5)
        canvas.line(2.5 * cm, 0.65 * inch, A4[0] - 2.5 * cm, 0.65 * inch)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    PAGE_W = A4[0] - 5 * cm  # usable width

    def S(name, **kw):
        base = kw.pop("parent", styles["Normal"])
        return ParagraphStyle(name, parent=base, **kw)

    title_s = S(
        "T", fontSize=34, textColor=JUNO_BLUE, alignment=1, fontName="Helvetica-Bold", spaceAfter=6
    )
    subtitle_s = S("ST", fontSize=12, textColor=JUNO_GRAY, alignment=1, spaceAfter=4)
    section_s = S(
        "SEC",
        fontSize=13,
        textColor=JUNO_BLUE,
        fontName="Helvetica-Bold",
        spaceBefore=14,
        spaceAfter=6,
    )
    body_s = S("B", fontSize=10, textColor=colors.HexColor("#333333"), leading=16, spaceAfter=4)
    gold_num_s = S(
        "GN", fontSize=48, textColor=JUNO_GOLD, fontName="Helvetica-Bold", alignment=1, spaceAfter=2
    )
    label_s = S("LB", fontSize=10, textColor=JUNO_GRAY, alignment=1)
    small_s = S("SM", fontSize=8, textColor=JUNO_GRAY, spaceAfter=2)
    conf_s = S("CF", fontSize=11, textColor=JUNO_RED, alignment=1, fontName="Helvetica-Bold")
    th_s = S("TH", fontSize=10, textColor=JUNO_WHITE, fontName="Helvetica-Bold")
    th_c_s = S("THC", fontSize=10, textColor=JUNO_WHITE, fontName="Helvetica-Bold", alignment=1)
    th_r_s = S("THR", fontSize=10, textColor=JUNO_WHITE, fontName="Helvetica-Bold", alignment=2)

    def hr():
        return HRFlowable(width="100%", thickness=1, color=JUNO_BLUE, spaceAfter=10, spaceBefore=2)

    def gold_hr():
        return HRFlowable(
            width="100%", thickness=1.5, color=JUNO_GOLD, spaceAfter=10, spaceBefore=2
        )

    elements = []

    # ─────────────────────────────────────────────────────────────────────────
    # 1. CAPA
    # ─────────────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 2.2 * inch))
    elements.append(Paragraph("JUNO", title_s))
    elements.append(Paragraph("DIAGNÓSTICO INDUSTRIAL EXECUTIVO", subtitle_s))
    elements.append(gold_hr())
    elements.append(Spacer(1, 0.5 * inch))

    cover_rows = [
        [Paragraph(f"<b>Empresa:</b>  {company_name}", body_s)],
        [Paragraph(f"<b>Data de Emissão:</b>  {date.today().strftime('%d/%m/%Y')}", body_s)],
        [Paragraph("<b>Versão:</b>  Juno v0.2.1", body_s)],
    ]
    cover_t = Table(cover_rows, colWidths=[4.5 * inch])
    cover_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), JUNO_LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("BOX", (0, 0), (-1, -1), 1, JUNO_BLUE),
                ("LINEAFTER", (0, 0), (0, -1), 3, JUNO_GOLD),
            ]
        )
    )
    elements.append(cover_t)
    elements.append(Spacer(1, 1.5 * inch))
    elements.append(Paragraph("⚠  CONFIDENCIAL — USO EXCLUSIVO DA DIRETORIA", conf_s))
    elements.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 2. SCORE EXECUTIVO
    # ─────────────────────────────────────────────────────────────────────────
    score = get_score_calculator(db).calculate_full_score(company_id, persist=False).overall_score
    status = _score_label(score)
    score_col = _score_color(score)

    elements.append(Paragraph("1. Score Executivo Juno", section_s))
    elements.append(hr())

    # 10-segment gauge bar
    filled = max(1, round(score / 10))
    bar_data = [[""] * 10]
    bar_t = Table(bar_data, colWidths=[0.56 * inch] * 10, rowHeights=[0.32 * inch])
    bar_style = [
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]
    for i in range(10):
        c = score_col if i < filled else colors.HexColor("#E5E7EB")
        bar_style.append(("BACKGROUND", (i, 0), (i, 0), c))
    bar_t.setStyle(TableStyle(bar_style))
    elements.append(bar_t)
    elements.append(Spacer(1, 0.15 * inch))

    elements.append(Paragraph(str(score), gold_num_s))
    elements.append(Paragraph("/100", label_s))
    elements.append(Spacer(1, 0.12 * inch))

    status_t = Table(
        [
            [
                Paragraph(
                    f"  {status}  ",
                    S(
                        "STS",
                        fontSize=13,
                        textColor=JUNO_WHITE,
                        fontName="Helvetica-Bold",
                        alignment=1,
                    ),
                )
            ]
        ],
        colWidths=[3 * inch],
    )
    status_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), score_col),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    elements.append(status_t)
    elements.append(Spacer(1, 0.4 * inch))

    # ─────────────────────────────────────────────────────────────────────────
    # 3. RESUMO EXECUTIVO
    # ─────────────────────────────────────────────────────────────────────────
    company_insights = insights.generate_insights(company_id, db)
    neg_margin_count = sum(1 for i in company_insights if i["type"] == "margin_risk")
    delays_count = _delays_from_insights(company_insights)

    elements.append(Paragraph("2. Resumo Executivo", section_s))
    elements.append(hr())
    elements.append(
        Paragraph(
            _executive_narrative(
                score, company_name, len(company_insights), delays_count, neg_margin_count
            ),
            body_s,
        )
    )
    elements.append(Spacer(1, 0.1 * inch))

    if company_insights:
        for ins in company_insights:
            dot_color = JUNO_RED if ins["impact"] == "Alto" else JUNO_YELLOW
            elements.append(
                Paragraph(
                    f"• {ins['message']}",
                    S("BL", parent=body_s, textColor=dot_color, leftIndent=10),
                )
            )
    elements.append(Spacer(1, 0.35 * inch))

    # ─────────────────────────────────────────────────────────────────────────
    # 4. INSIGHTS CRÍTICOS
    # ─────────────────────────────────────────────────────────────────────────
    elements.append(Paragraph("3. Insights Críticos e Riscos Detectados", section_s))
    elements.append(hr())

    if company_insights:
        rows = [
            [
                Paragraph("Risco Identificado", th_s),
                Paragraph("Impacto", th_c_s),
                Paragraph("Ação Recomendada", th_s),
            ]
        ]
        for ins in company_insights:
            ic = JUNO_RED if ins["impact"] == "Alto" else JUNO_YELLOW
            rows.append(
                [
                    Paragraph(ins["message"], body_s),
                    Paragraph(
                        f"<b>{ins['impact']}</b>", S("IC", parent=body_s, textColor=ic, alignment=1)
                    ),
                    Paragraph(ins["action"], body_s),
                ]
            )
        t = Table(rows, colWidths=[2.8 * inch, 0.9 * inch, 2.8 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), JUNO_BLUE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [JUNO_LIGHT, JUNO_WHITE]),
                    ("ALIGN", (1, 0), (1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ("BOX", (0, 0), (-1, -1), 1, JUNO_BLUE),
                ]
            )
        )
        elements.append(t)
    else:
        elements.append(Paragraph("Nenhum risco crítico detectado no período analisado.", body_s))
    elements.append(Spacer(1, 0.4 * inch))

    # ─────────────────────────────────────────────────────────────────────────
    # 5. ANÁLISE DE MARGEM POR PRODUTO
    # ─────────────────────────────────────────────────────────────────────────
    cfo_data = dashboards.get_cfo_margin_by_product(db, company_id)
    elements.append(Paragraph("4. Análise de Margem por Produto", section_s))
    elements.append(hr())

    if cfo_data:
        mrows = [
            [
                Paragraph("Produto", th_s),
                Paragraph("Receita Líquida", th_r_s),
                Paragraph("Custo Real", th_r_s),
                Paragraph("Margem", th_r_s),
            ]
        ]
        for row in cfo_data:
            mc = JUNO_RED if row["margem"] < 0 else JUNO_GREEN
            mrows.append(
                [
                    Paragraph(row["product"], body_s),
                    Paragraph(
                        f"R$ {row['receita_liquida']:,.0f}", S("RR", parent=body_s, alignment=2)
                    ),
                    Paragraph(f"R$ {row['custo_real']:,.0f}", S("CR", parent=body_s, alignment=2)),
                    Paragraph(
                        f"<b>R$ {row['margem']:,.0f}</b>",
                        S("MR", parent=body_s, textColor=mc, alignment=2),
                    ),
                ]
            )
        mt = Table(mrows, colWidths=[2.2 * inch, 1.5 * inch, 1.4 * inch, 1.4 * inch])
        mt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), JUNO_BLUE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [JUNO_LIGHT, JUNO_WHITE]),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ("BOX", (0, 0), (-1, -1), 1, JUNO_BLUE),
                ]
            )
        )
        elements.append(mt)
    elements.append(Spacer(1, 0.4 * inch))

    # ─────────────────────────────────────────────────────────────────────────
    # 6. IMPACTO FINANCEIRO
    # ─────────────────────────────────────────────────────────────────────────
    ceo_data = dashboards.get_ceo_kpis(db, company_id)
    revenue = ceo_data["receita_liquida"]

    margin_loss = sum(abs(r["margem"]) for r in cfo_data if r["margem"] < 0)
    delay_loss = delays_count * (revenue * 0.005) if revenue > 0 else 0
    efficiency_loss = (
        (revenue * 0.02) if any(i["type"] == "cost_risk" for i in company_insights) else 0
    )
    total_loss = margin_loss + delay_loss + efficiency_loss

    elements.append(Paragraph("5. Impacto Financeiro Estimado", section_s))
    elements.append(hr())

    irows = [
        [Paragraph("Componente de Perda", th_s), Paragraph("Perda Estimada / Mês", th_r_s)],
        [
            Paragraph("Perda de Margem em Produtos Críticos", body_s),
            Paragraph(f"R$ {margin_loss:,.0f}", S("V", parent=body_s, alignment=2)),
        ],
        [
            Paragraph(f"Custo de Atrasos ({delays_count} ordens)", body_s),
            Paragraph(f"R$ {delay_loss:,.0f}", S("V", parent=body_s, alignment=2)),
        ],
        [
            Paragraph("Ineficiência Produtiva (estimada)", body_s),
            Paragraph(f"R$ {efficiency_loss:,.0f}", S("V", parent=body_s, alignment=2)),
        ],
        [
            Paragraph(
                "<b>TOTAL ESTIMADO</b>",
                S("TOT", parent=body_s, fontName="Helvetica-Bold", textColor=JUNO_RED),
            ),
            Paragraph(
                f"<b>R$ {total_loss:,.0f}</b>",
                S(
                    "TOTR",
                    parent=body_s,
                    fontName="Helvetica-Bold",
                    textColor=JUNO_RED,
                    alignment=2,
                ),
            ),
        ],
    ]
    it = Table(irows, colWidths=[4.2 * inch, 2.3 * inch])
    it.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), JUNO_BLUE),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEF2F2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [JUNO_LIGHT, JUNO_WHITE]),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("BOX", (0, 0), (-1, -1), 1.5, JUNO_RED),
            ]
        )
    )
    elements.append(it)
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(
        Paragraph(
            "* Estimativas baseadas em desvios de margem, atrasos operacionais e "
            "custo de ineficiência detectados pelo Juno.",
            small_s,
        )
    )
    elements.append(Spacer(1, 0.4 * inch))

    # ─────────────────────────────────────────────────────────────────────────
    # 7. RECOMENDAÇÕES ESTRATÉGICAS
    # ─────────────────────────────────────────────────────────────────────────
    elements.append(Paragraph("6. Recomendações Estratégicas", section_s))
    elements.append(hr())

    recs = [i["action"] for i in company_insights] or [
        "Manter monitoramento contínuo dos indicadores operacionais."
    ]
    rec_rows = [[Paragraph(f"{idx+1}.  {rec}", body_s)] for idx, rec in enumerate(recs)]
    rt = Table(rec_rows, colWidths=[PAGE_W])
    rt.setStyle(
        TableStyle(
            [
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [JUNO_LIGHT, JUNO_WHITE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("BOX", (0, 0), (-1, -1), 1, JUNO_BLUE),
                ("LINEAFTER", (0, 0), (0, -1), 3, JUNO_GOLD),
            ]
        )
    )
    elements.append(rt)
    elements.append(Spacer(1, 0.4 * inch))

    # ─────────────────────────────────────────────────────────────────────────
    # 8. PLANO DE AÇÃO — 30 / 90 DIAS
    # ─────────────────────────────────────────────────────────────────────────
    elements.append(Paragraph("7. Plano de Ação", section_s))
    elements.append(hr())

    short_term = (
        "• Reunião de alinhamento com direção comercial e produção\n"
        "• Revisão imediata da precificação dos produtos com margem negativa\n"
        "• Mapeamento das causas-raiz dos atrasos nas ordens críticas"
    )
    mid_term = (
        "• Implementação de política de gestão de custos industriais\n"
        "• Auditoria de desperdícios na linha de produção\n"
        "• Negociação com fornecedores para redução de insumos críticos\n"
        "• Implantação de monitoramento contínuo via Juno Dashboard"
    )

    plan_rows = [
        [Paragraph("Horizonte", th_s), Paragraph("Ações Prioritárias", th_s)],
        [
            Paragraph(
                "Curto Prazo\n(30 dias)",
                S(
                    "HP30",
                    parent=body_s,
                    textColor=JUNO_BLUE,
                    fontName="Helvetica-Bold",
                    alignment=1,
                ),
            ),
            Paragraph(short_term, body_s),
        ],
        [
            Paragraph(
                "Médio Prazo\n(90 dias)",
                S(
                    "HP90",
                    parent=body_s,
                    textColor=JUNO_BLUE,
                    fontName="Helvetica-Bold",
                    alignment=1,
                ),
            ),
            Paragraph(mid_term, body_s),
        ],
    ]
    pt = Table(plan_rows, colWidths=[1.5 * inch, PAGE_W - 1.5 * inch])
    pt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), JUNO_BLUE),
                ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#FFF8E7")),
                ("BACKGROUND", (0, 2), (0, 2), colors.HexColor("#EBF5FB")),
                ("BACKGROUND", (1, 1), (1, 1), colors.HexColor("#FEFCE8")),
                ("BACKGROUND", (1, 2), (1, 2), colors.HexColor("#EFF6FF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("BOX", (0, 0), (-1, -1), 1, JUNO_BLUE),
            ]
        )
    )
    elements.append(pt)
    elements.append(Spacer(1, 0.5 * inch))

    # ─────────────────────────────────────────────────────────────────────────
    # Rodapé de marca
    # ─────────────────────────────────────────────────────────────────────────
    elements.append(gold_hr())
    elements.append(
        Paragraph(
            "Gerado por JUNO — Plataforma de Diagnóstico Industrial  |  gravithy.com.br",
            S("BRAND", parent=styles["Normal"], fontSize=9, textColor=JUNO_GRAY, alignment=1),
        )
    )

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer
