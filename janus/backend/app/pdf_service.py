"""
JUNO PDF Service v2.0 — Relatório Executivo Completo
Inclui: KPIs operacionais, Score JUNO 2.0, DRE, Balanço, DFC, gráficos
"""

import io
from datetime import datetime

from fastapi import Depends
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, FinancialStatement
from app.score_v2 import JunoScoreCalculator

try:
    from app import templates_financeiro
except ImportError:  # pragma: no cover
    templates_financeiro = None  # type: ignore[assignment]

JUNO_NAVY = colors.HexColor("#0A2342")
JUNO_GOLD = colors.HexColor("#C9A959")

# Strings do relatorio por idioma (Fase 2 — PDF trilingue). PT e o padrao; o
# idioma chega via parametro lang em generate_executive_report (vindo do seletor
# da UI). Valores monetarios permanecem em R$.
PDF_I18N: dict[str, dict[str, str]] = {
    "pt": {
        "executiveReport": "Relatório Executivo",
        "company": "Empresa:",
        "sector": "Setor:",
        "date": "Data:",
        "scoreJuno": "Score JUNO",
        "trend": "Tendência: {trend} ({delta})",
        "scoreTrend": "Score {trend}",
        "componentAnalysis": "Análise por Componentes",
        "colComponent": "Componente",
        "colWeight": "Peso",
        "colScore": "Score",
        "colStatus": "Status",
        "colDetails": "Detalhes",
        "recommendations": "Recomendações Executivas",
        "operationalDiagnosis": "Diagnóstico Operacional",
        "kpiRevenue": "Receita Líquida",
        "kpiScore": "Score JUNO",
        "kpiDelays": "Ordens Atrasadas",
        "kpiNegMargin": "Produtos Margem Negativa",
        "risksInsights": "Riscos e Insights",
        "noRisks": "Nenhum risco crítico detectado no momento.",
        "impact": "Impacto",
        "worstMargins": "Margem por Produto (5 piores)",
        "colProduct": "Produto",
        "colRevenue": "Receita",
        "colCost": "Custo",
        "colMargin": "Margem",
        "dreTitle": "Demonstração do Resultado do Exercício (DRE)",
        "balanceTitle": "Balanço Patrimonial",
        "dfcTitle": "Demonstração de Fluxo de Caixa (DFC)",
        "notAvailable": "{stmt} não disponível. Faça upload na aba Financials.",
        "colAccount": "Conta",
        "colIndicator": "Indicador",
        "colValue": "Valor",
        "colInterpretation": "Interpretação",
        "source": "Fonte: {source} · DRE/DFC {comp} · Balanço {pat}",
        "section": "Seção",
        "financialStatements": "Demonstrações Financeiras",
        "footer": "JUNO Industrial Diagnostic v2.0 | Gerado em {date} | Este relatório é confidencial e destinado exclusivamente à gestão da {company}.",
        "trendImproving": "Melhorando",
        "trendStable": "Estável",
        "trendDeclining": "Piorando",
        "statusExcellent": "Excelente",
        "statusGood": "Bom",
        "statusRegular": "Regular",
        "statusCritical": "Crítico",
        "interpHealthy": "Saudável",
        "interpAttention": "Atenção",
        "interpCritical": "Crítico",
        "interpExcellent": "Excelente",
        "interpGood": "Bom",
        "indGrossMargin": "Margem Bruta",
        "indEbitdaMargin": "Margem EBITDA",
        "indNetMargin": "Margem Líquida",
        "indCurrentLiquidity": "Liquidez Corrente",
        "indDebt": "Endividamento",
        "detailAvg": "Média",
        "detailNegatives": "Negativos",
        "detailDelays": "Atrasos",
        "detailCompleteness": "Completude",
        "detailTop3": "Top3",
        "seeDetails": "Ver detalhes",
        "compMargin": "Margem",
        "compLiquidity": "Liquidez",
        "compDebt": "Endividamento",
        "compProduction": "Produção",
        "compDataQuality": "Qualidade de Dados",
        "compSeasonality": "Sazonalidade",
        "compCustomerConcentration": "Concentração de Clientes",
    },
    "en": {
        "executiveReport": "Executive Report",
        "company": "Company:",
        "sector": "Sector:",
        "date": "Date:",
        "scoreJuno": "JUNO Score",
        "trend": "Trend: {trend} ({delta})",
        "scoreTrend": "Score {trend}",
        "componentAnalysis": "Component Analysis",
        "colComponent": "Component",
        "colWeight": "Weight",
        "colScore": "Score",
        "colStatus": "Status",
        "colDetails": "Details",
        "recommendations": "Executive Recommendations",
        "operationalDiagnosis": "Operational Diagnosis",
        "kpiRevenue": "Net Revenue",
        "kpiScore": "JUNO Score",
        "kpiDelays": "Delayed Orders",
        "kpiNegMargin": "Negative Margin Products",
        "risksInsights": "Risks and Insights",
        "noRisks": "No critical risk detected at the moment.",
        "impact": "Impact",
        "worstMargins": "Margin by Product (5 worst)",
        "colProduct": "Product",
        "colRevenue": "Revenue",
        "colCost": "Cost",
        "colMargin": "Margin",
        "dreTitle": "Income Statement (P&L)",
        "balanceTitle": "Balance Sheet",
        "dfcTitle": "Cash Flow Statement",
        "notAvailable": "{stmt} not available. Upload it in the Financials tab.",
        "colAccount": "Account",
        "colIndicator": "Indicator",
        "colValue": "Value",
        "colInterpretation": "Interpretation",
        "source": "Source: {source} · P&L/CF {comp} · Balance {pat}",
        "section": "Section",
        "financialStatements": "Financial Statements",
        "footer": "JUNO Industrial Diagnostic v2.0 | Generated on {date} | This report is confidential and intended exclusively for the management of {company}.",
        "trendImproving": "Improving",
        "trendStable": "Stable",
        "trendDeclining": "Declining",
        "statusExcellent": "Excellent",
        "statusGood": "Good",
        "statusRegular": "Fair",
        "statusCritical": "Critical",
        "interpHealthy": "Healthy",
        "interpAttention": "Attention",
        "interpCritical": "Critical",
        "interpExcellent": "Excellent",
        "interpGood": "Good",
        "indGrossMargin": "Gross Margin",
        "indEbitdaMargin": "EBITDA Margin",
        "indNetMargin": "Net Margin",
        "indCurrentLiquidity": "Current Ratio",
        "indDebt": "Leverage",
        "detailAvg": "Avg",
        "detailNegatives": "Negatives",
        "detailDelays": "Delays",
        "detailCompleteness": "Completeness",
        "detailTop3": "Top3",
        "seeDetails": "See details",
        "compMargin": "Margin",
        "compLiquidity": "Liquidity",
        "compDebt": "Leverage",
        "compProduction": "Production",
        "compDataQuality": "Data Quality",
        "compSeasonality": "Seasonality",
        "compCustomerConcentration": "Customer Concentration",
    },
    "es": {
        "executiveReport": "Informe Ejecutivo",
        "company": "Empresa:",
        "sector": "Sector:",
        "date": "Fecha:",
        "scoreJuno": "Score JUNO",
        "trend": "Tendencia: {trend} ({delta})",
        "scoreTrend": "Score {trend}",
        "componentAnalysis": "Análisis por Componentes",
        "colComponent": "Componente",
        "colWeight": "Peso",
        "colScore": "Score",
        "colStatus": "Estado",
        "colDetails": "Detalles",
        "recommendations": "Recomendaciones Ejecutivas",
        "operationalDiagnosis": "Diagnóstico Operacional",
        "kpiRevenue": "Ingreso Neto",
        "kpiScore": "Score JUNO",
        "kpiDelays": "Órdenes Atrasadas",
        "kpiNegMargin": "Productos Margen Negativo",
        "risksInsights": "Riesgos e Insights",
        "noRisks": "Ningún riesgo crítico detectado en este momento.",
        "impact": "Impacto",
        "worstMargins": "Margen por Producto (5 peores)",
        "colProduct": "Producto",
        "colRevenue": "Ingreso",
        "colCost": "Costo",
        "colMargin": "Margen",
        "dreTitle": "Estado de Resultados (ER)",
        "balanceTitle": "Balance General",
        "dfcTitle": "Estado de Flujo de Caja",
        "notAvailable": "{stmt} no disponible. Cárguelo en la pestaña Financials.",
        "colAccount": "Cuenta",
        "colIndicator": "Indicador",
        "colValue": "Valor",
        "colInterpretation": "Interpretación",
        "source": "Fuente: {source} · ER/FC {comp} · Balance {pat}",
        "section": "Sección",
        "financialStatements": "Estados Financieros",
        "footer": "JUNO Industrial Diagnostic v2.0 | Generado el {date} | Este informe es confidencial y destinado exclusivamente a la gestión de {company}.",
        "trendImproving": "Mejorando",
        "trendStable": "Estable",
        "trendDeclining": "Empeorando",
        "statusExcellent": "Excelente",
        "statusGood": "Bueno",
        "statusRegular": "Regular",
        "statusCritical": "Crítico",
        "interpHealthy": "Saludable",
        "interpAttention": "Atención",
        "interpCritical": "Crítico",
        "interpExcellent": "Excelente",
        "interpGood": "Bueno",
        "indGrossMargin": "Margen Bruto",
        "indEbitdaMargin": "Margen EBITDA",
        "indNetMargin": "Margen Neto",
        "indCurrentLiquidity": "Liquidez Corriente",
        "indDebt": "Endeudamiento",
        "detailAvg": "Prom",
        "detailNegatives": "Negativos",
        "detailDelays": "Retrasos",
        "detailCompleteness": "Completitud",
        "detailTop3": "Top3",
        "seeDetails": "Ver detalles",
        "compMargin": "Margen",
        "compLiquidity": "Liquidez",
        "compDebt": "Endeudamiento",
        "compProduction": "Producción",
        "compDataQuality": "Calidad de Datos",
        "compSeasonality": "Estacionalidad",
        "compCustomerConcentration": "Concentración de Clientes",
    },
}


class JUNOPDFReport:
    """
    Gerador de relatórios PDF executivos.
    """

    def __init__(self, db: Session, lang: str = "pt"):
        self.db = db
        self.lang = lang if lang in PDF_I18N else "pt"
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _t(self, key: str, **vars: object) -> str:
        """Traduz uma chave para o idioma do relatorio, com interpolacao {var}."""
        text = PDF_I18N.get(self.lang, PDF_I18N["pt"]).get(key) or PDF_I18N["pt"].get(key, key)
        if vars:
            try:
                return text.format(**vars)
            except (KeyError, IndexError):
                return text
        return text

    def _setup_custom_styles(self):
        """Configura estilos customizados."""
        self.styles.add(
            ParagraphStyle(
                name="JUNO_Title",
                parent=self.styles["Heading1"],
                fontSize=24,
                textColor=JUNO_NAVY,
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="JUNO_Section",
                parent=self.styles["Heading2"],
                fontSize=16,
                textColor=JUNO_NAVY,
                spaceAfter=12,
                spaceBefore=20,
                fontName="Helvetica-Bold",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="JUNO_SubSection",
                parent=self.styles["Heading3"],
                fontSize=13,
                textColor=JUNO_NAVY,
                spaceAfter=8,
                fontName="Helvetica-Bold",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="JUNO_Body",
                parent=self.styles["BodyText"],
                fontSize=10,
                leading=14,
                alignment=TA_JUSTIFY,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="JUNO_Score",
                parent=self.styles["Normal"],
                fontSize=48,
                textColor=JUNO_NAVY,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="JUNO_ScoreLabel",
                parent=self.styles["Normal"],
                fontSize=12,
                textColor=colors.HexColor("#64748b"),
                alignment=TA_CENTER,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="JUNO_Alert",
                parent=self.styles["Normal"],
                fontSize=10,
                textColor=colors.HexColor("#dc2626"),
                backColor=colors.HexColor("#fef2f2"),
                borderColor=colors.HexColor("#fecaca"),
                borderWidth=1,
                borderPadding=8,
                spaceAfter=10,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="JUNO_Success",
                parent=self.styles["Normal"],
                fontSize=10,
                textColor=colors.HexColor("#16a34a"),
                backColor=colors.HexColor("#f0fdf4"),
                borderColor=colors.HexColor("#bbf7d0"),
                borderWidth=1,
                borderPadding=8,
                spaceAfter=10,
            )
        )

    def generate_executive_report(self, company_id: int, lang: str = "pt") -> bytes:
        """
        Gera relatório executivo completo em PDF. lang: pt|en|es (Fase 2).
        """
        if lang in PDF_I18N:
            self.lang = lang
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ValueError(f"Empresa {company_id} não encontrada")

        # Calcular Score JUNO 2.0
        calculator = JunoScoreCalculator(self.db)
        score_result = calculator.calculate_full_score(company_id)

        # Buffer de memória
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        story = []

        # ============================================================
        # CAPA
        # ============================================================
        story.append(Spacer(1, 3 * cm))
        story.append(Paragraph("JUNO", self.styles["JUNO_Title"]))
        story.append(Paragraph("Industrial Diagnostic", self.styles["JUNO_Title"]))
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(self._t("executiveReport"), self.styles["JUNO_Section"]))
        story.append(Spacer(1, 0.5 * cm))
        story.append(
            Paragraph(f"<b>{self._t('company')}</b> {company.name}", self.styles["JUNO_Body"])
        )
        story.append(
            Paragraph(f"<b>{self._t('sector')}</b> {company.sector}", self.styles["JUNO_Body"])
        )
        story.append(
            Paragraph(
                f"<b>{self._t('date')}</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                self.styles["JUNO_Body"],
            )
        )
        story.append(Spacer(1, 2 * cm))

        # Score JUNO
        score_color = self._get_score_color(score_result.overall_score)
        story.append(Paragraph(f"{score_result.overall_score:.0f}", self.styles["JUNO_Score"]))
        story.append(Paragraph(self._t("scoreJuno"), self.styles["JUNO_ScoreLabel"]))
        story.append(
            Paragraph(
                self._t(
                    "trend",
                    trend=self._translate_trend(score_result.trend),
                    delta=f"{score_result.trend_delta:+.1f}",
                ),
                self.styles["JUNO_ScoreLabel"],
            )
        )
        story.append(Spacer(1, 1 * cm))

        # Tendência visual
        trend_arrow = (
            "↑"
            if score_result.trend == "improving"
            else "↓" if score_result.trend == "declining" else "→"
        )
        story.append(
            Paragraph(
                f"<font size='14' color='{score_color}'>{trend_arrow} "
                f"{self._t('scoreTrend', trend=self._translate_trend(score_result.trend))}</font>",
                self.styles["JUNO_ScoreLabel"],
            )
        )

        story.append(PageBreak())

        # ============================================================
        # COMPONENTES DO SCORE
        # ============================================================
        story.append(Paragraph(self._t("componentAnalysis"), self.styles["JUNO_Section"]))
        story.append(Spacer(1, 0.5 * cm))

        # Tabela de componentes
        comp_data = [
            [
                self._t("colComponent"),
                self._t("colWeight"),
                self._t("colScore"),
                self._t("colStatus"),
                self._t("colDetails"),
            ]
        ]
        for comp in score_result.components:
            status = self._get_status_text(comp.normalized_score)
            detail_text = self._format_detail(comp.name, comp.details)
            comp_data.append(
                [
                    self._translate_component(comp.name),
                    f"{comp.weight*100:.0f}%",
                    f"{comp.normalized_score:.0f}/100",
                    status,
                    detail_text,
                ]
            )

        comp_table = Table(comp_data, colWidths=[3 * cm, 2 * cm, 2.5 * cm, 2.5 * cm, 6 * cm])
        comp_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("ALIGN", (4, 1), (4, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#f8fafc"), colors.HexColor("#ffffff")],
                    ),
                ]
            )
        )
        story.append(comp_table)
        story.append(Spacer(1, 1 * cm))

        # ============================================================
        # RECOMENDAÇÕES
        # ============================================================
        story.append(Paragraph(self._t("recommendations"), self.styles["JUNO_Section"]))
        for rec in score_result.recommendations:
            if "🔴" in rec:
                story.append(Paragraph(rec, self.styles["JUNO_Alert"]))
            elif "🟡" in rec:
                story.append(Paragraph(rec, self.styles["JUNO_Alert"]))
            else:
                story.append(Paragraph(rec, self.styles["JUNO_Success"]))
        story.append(Spacer(1, 1 * cm))

        story.append(PageBreak())

        # ============================================================
        # DIAGNÓSTICO OPERACIONAL (KPIs, riscos e margens) — espelha a tela
        # ============================================================
        self._add_operational_diagnosis(story, company_id)

        story.append(PageBreak())

        # ============================================================
        # DEMONSTRAÇÕES FINANCEIRAS
        # ============================================================
        self._add_financial_statements(story, company_id)

        story.append(PageBreak())

        # ============================================================
        # RODAPÉ
        # ============================================================
        story.append(
            Paragraph(
                f"<font size='8' color='grey'>"
                f"{self._t('footer', date=datetime.now().strftime('%d/%m/%Y %H:%M'), company=company.name)}"
                f"</font>",
                self.styles["JUNO_ScoreLabel"],
            )
        )

        # Build PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def _translate_component(self, name: str) -> str:
        """Traduz o nome do componente do score (vem do score_v2 em PT)."""
        mapping = {
            "Margem": "compMargin",
            "Liquidez": "compLiquidity",
            "Endividamento": "compDebt",
            "Produção": "compProduction",
            "Qualidade de Dados": "compDataQuality",
            "Sazonalidade": "compSeasonality",
            "Concentração de Clientes": "compCustomerConcentration",
        }
        key = mapping.get(name)
        return self._t(key) if key else name

    def _add_operational_diagnosis(self, story: list, company_id: int) -> None:
        """Seção operacional (KPIs, riscos e margens) — espelha o que aparece na tela.

        Antes o PDF tinha apenas score + financeiro; faltava o diagnostico
        operacional do dashboard (causa do 'relatorio incompleto').
        """
        from app.dashboards import get_ceo_kpis, get_cfo_margin_by_product
        from app.insights import generate_insights

        story.append(Paragraph(self._t("operationalDiagnosis"), self.styles["JUNO_Section"]))
        story.append(Spacer(1, 0.4 * cm))

        ceo = get_ceo_kpis(self.db, company_id)
        margins = get_cfo_margin_by_product(self.db, company_id)
        neg_margin = sum(1 for m in margins if float(m.get("margem", 0)) < 0)
        try:
            from app.dashboards import get_coo_delayed_orders

            delayed = len(get_coo_delayed_orders(self.db, company_id))
        except Exception:
            delayed = 0

        kpi_data = [
            [self._t("kpiRevenue"), f"R$ {float(ceo.get('receita_liquida') or 0):,.2f}"],
            [self._t("kpiScore"), f"{float(ceo.get('score_juno') or 0):.0f}/100"],
            [self._t("kpiDelays"), str(delayed)],
            [self._t("kpiNegMargin"), str(neg_margin)],
        ]
        kpi_table = Table(kpi_data, colWidths=[9 * cm, 7 * cm])
        kpi_table.setStyle(self._get_indicator_table_style())
        story.append(kpi_table)
        story.append(Spacer(1, 0.6 * cm))

        # Riscos e insights
        story.append(Paragraph(self._t("risksInsights"), self.styles["JUNO_SubSection"]))
        insights = generate_insights(company_id, self.db)
        if insights:
            for ins in insights[:6]:
                msg = ins.get("message", "")
                impact = ins.get("impact", "")
                story.append(
                    Paragraph(
                        f"• {msg} <font color='grey'>({self._t('impact')}: {impact})</font>",
                        self.styles["JUNO_Body"],
                    )
                )
        else:
            story.append(Paragraph(self._t("noRisks"), self.styles["JUNO_Success"]))
        story.append(Spacer(1, 0.6 * cm))

        # Margem por produto (5 piores) — margins ja vem ordenado asc por margem
        if margins:
            story.append(Paragraph(self._t("worstMargins"), self.styles["JUNO_SubSection"]))
            margin_rows = [
                [
                    self._t("colProduct"),
                    self._t("colRevenue"),
                    self._t("colCost"),
                    self._t("colMargin"),
                ]
            ]
            for m in margins[:5]:
                margin_rows.append(
                    [
                        str(m.get("product", "")),
                        f"R$ {float(m.get('receita_liquida', 0)):,.0f}",
                        f"R$ {float(m.get('custo_real', 0)):,.0f}",
                        f"R$ {float(m.get('margem', 0)):,.0f}",
                    ]
                )
            margin_table = Table(margin_rows, colWidths=[7 * cm, 3 * cm, 3 * cm, 3 * cm])
            margin_table.setStyle(self._get_indicator_table_style())
            story.append(margin_table)

    def _add_financial_statements(self, story: list, company_id: int):
        """Adiciona DRE, Balanço e DFC ao relatório."""
        if templates_financeiro and templates_financeiro.use_templates_as_canonical():
            relatorio = templates_financeiro.build_demonstracoes_relatorio()
            if relatorio:
                self._add_template_report(story, relatorio)
                return

        # DRE
        story.append(Paragraph(self._t("dreTitle"), self.styles["JUNO_Section"]))

        dre_data = self._get_dre_data(company_id)
        if dre_data:
            dre_table = self._create_financial_table(dre_data, "DRE")
            story.append(dre_table)
            story.append(Spacer(1, 0.5 * cm))

            # Indicadores DRE
            indicators = self._calculate_dre_indicators(dre_data)
            ind_data = [
                [self._t("colIndicator"), self._t("colValue"), self._t("colInterpretation")]
            ]
            for ind in indicators:
                ind_data.append([ind["name"], ind["value"], ind["interpretation"]])

            ind_table = Table(ind_data, colWidths=[5 * cm, 3 * cm, 8 * cm])
            ind_table.setStyle(self._get_indicator_table_style())
            story.append(ind_table)
        else:
            story.append(Paragraph(self._t("notAvailable", stmt="DRE"), self.styles["JUNO_Alert"]))

        story.append(Spacer(1, 1 * cm))

        # Balanço
        story.append(Paragraph(self._t("balanceTitle"), self.styles["JUNO_Section"]))

        balance_data = self._get_balance_data(company_id)
        if balance_data:
            bal_table = self._create_financial_table(balance_data, "Balanco")
            story.append(bal_table)
            story.append(Spacer(1, 0.5 * cm))

            # Indicadores de estrutura
            structure = self._calculate_structure_indicators(balance_data)
            struct_data = [
                [self._t("colIndicator"), self._t("colValue"), self._t("colInterpretation")]
            ]
            for s in structure:
                struct_data.append([s["name"], s["value"], s["interpretation"]])

            struct_table = Table(struct_data, colWidths=[5 * cm, 3 * cm, 8 * cm])
            struct_table.setStyle(self._get_indicator_table_style())
            story.append(struct_table)
        else:
            story.append(
                Paragraph(
                    self._t("notAvailable", stmt=self._t("balanceTitle")),
                    self.styles["JUNO_Alert"],
                )
            )

        story.append(Spacer(1, 1 * cm))

        # DFC
        story.append(Paragraph(self._t("dfcTitle"), self.styles["JUNO_Section"]))

        dfc_data = self._get_dfc_data(company_id)
        if dfc_data:
            dfc_table = self._create_financial_table(dfc_data, "DFC")
            story.append(dfc_table)
        else:
            story.append(Paragraph(self._t("notAvailable", stmt="DFC"), self.styles["JUNO_Alert"]))

    def _add_template_report(self, story: list, relatorio: dict) -> None:
        """Renderiza demonstrações no layout do modelo Templates."""
        story.append(
            Paragraph(
                f"{relatorio.get('titulo', self._t('financialStatements'))} "
                f"({relatorio.get('unidade', 'R$ milhões')})",
                self.styles["JUNO_Section"],
            )
        )
        story.append(
            Paragraph(
                self._t(
                    "source",
                    source=relatorio.get("fonte", "Templates"),
                    comp=relatorio.get("competencia", ""),
                    pat=relatorio.get("patrimonial", ""),
                ),
                self.styles["JUNO_Body"],
            )
        )
        story.append(Spacer(1, 0.4 * cm))

        for secao in relatorio.get("secoes", []):
            story.append(
                Paragraph(secao.get("titulo", self._t("section")), self.styles["JUNO_SubSection"])
            )
            table = self._create_template_table(secao)
            story.append(table)
            story.append(Spacer(1, 0.5 * cm))

    def _create_template_table(self, secao: dict) -> Table:
        periodos = secao.get("periodos") or []
        header = [self._t("colAccount"), *periodos]
        table_data = [header]

        for linha in secao.get("linhas", []):
            row = [linha.get("conta", "")]
            unit = linha.get("unit")
            for valor in linha.get("valores") or []:
                if valor is None:
                    row.append("—")
                elif unit == "percent":
                    row.append(f"{float(valor):.2f}%")
                elif unit == "ratio":
                    row.append(f"{float(valor):.2f}x")
                elif unit == "score":
                    row.append(f"{float(valor):.1f}/100")
                else:
                    row.append(f"R$ {float(valor):,.2f} mi")
            table_data.append(row)

        col_widths = [7 * cm] + [2.5 * cm] * len(periodos)
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), JUNO_NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#f8fafc"), colors.white],
                    ),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ]
            )
        )
        return table

    def _get_dre_data(self, company_id: int) -> list[dict]:
        """Busca dados da DRE no banco."""
        statements = (
            self.db.query(FinancialStatement)
            .filter(
                FinancialStatement.company_id == company_id,
                FinancialStatement.statement_type == "DRE",
            )
            .order_by(FinancialStatement.period)
            .all()
        )

        return [
            {"period": s.period, "line_item": s.line_item, "value": s.value} for s in statements
        ]

    def _get_balance_data(self, company_id: int) -> list[dict]:
        """Busca dados do Balanço no banco."""
        statements = (
            self.db.query(FinancialStatement)
            .filter(
                FinancialStatement.company_id == company_id,
                # statement_type pode vir como 'Balanco' ou 'BALANCO' conforme o import
                FinancialStatement.statement_type.in_(["Balanco", "BALANCO", "balanco"]),
            )
            .order_by(FinancialStatement.period)
            .all()
        )

        return [
            {"period": s.period, "line_item": s.line_item, "value": s.value} for s in statements
        ]

    def _get_dfc_data(self, company_id: int) -> list[dict]:
        """Busca dados da DFC no banco."""
        statements = (
            self.db.query(FinancialStatement)
            .filter(
                FinancialStatement.company_id == company_id,
                FinancialStatement.statement_type == "DFC",
            )
            .order_by(FinancialStatement.period)
            .all()
        )

        return [
            {"period": s.period, "line_item": s.line_item, "value": s.value} for s in statements
        ]

    def _create_financial_table(self, data: list[dict], statement_type: str) -> Table:
        """Cria tabela formatada para demonstrações financeiras."""
        # Agrupar por período
        periods = sorted(list(set([d["period"] for d in data])))

        # Header
        header = [self._t("colAccount")] + periods

        # Linhas únicas
        line_items = sorted(list(set([d["line_item"] for d in data])))

        table_data = [header]
        for item in line_items:
            row = [item]
            for period in periods:
                value = next(
                    (d["value"] for d in data if d["line_item"] == item and d["period"] == period),
                    0,
                )
                row.append(f"R$ {value:,.2f}")
            table_data.append(row)

        # Larguras
        col_widths = [6 * cm] + [3 * cm] * len(periods)

        table = Table(table_data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#f8fafc"), colors.HexColor("#ffffff")],
                    ),
                    ("TOPPADDING", (0, 1), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ]
            )
        )

        return table

    def _get_indicator_table_style(self) -> TableStyle:
        """Retorna estilo padrão para tabelas de indicadores."""
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f0f9ff")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bae6fd")),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )

    def _calculate_dre_indicators(self, dre_data: list[dict]) -> list[dict]:
        """Calcula indicadores da DRE."""
        # Agrupar por período
        periods: dict[str, dict[str, float]] = {}
        for d in dre_data:
            if d["period"] not in periods:
                periods[d["period"]] = {}
            periods[d["period"]][d["line_item"]] = d["value"]

        # Usar período mais recente
        latest_period = max(periods.keys()) if periods else None
        if not latest_period:
            return []

        data = periods[latest_period]

        receita = data.get("receita_liquida", data.get("receita_bruta", 0))
        cmv = data.get("cmv", data.get("cpv", data.get("cogs", 0)))
        lucro_bruto = data.get("lucro_bruto", receita - cmv)
        ebitda = data.get("ebitda", 0)
        lucro_liquido = data.get("lucro_liquido", data.get("resultado_liquido", 0))

        indicators = []

        if receita > 0:
            indicators.append(
                {
                    "name": self._t("indGrossMargin"),
                    "value": f"{(lucro_bruto / receita * 100):.1f}%",
                    "interpretation": (
                        self._t("interpHealthy")
                        if lucro_bruto / receita > 0.3
                        else (
                            self._t("interpAttention")
                            if lucro_bruto / receita > 0.15
                            else self._t("interpCritical")
                        )
                    ),
                }
            )

            indicators.append(
                {
                    "name": self._t("indEbitdaMargin"),
                    "value": f"{(ebitda / receita * 100):.1f}%" if ebitda else "N/A",
                    "interpretation": (
                        self._t("interpHealthy")
                        if ebitda and ebitda / receita > 0.15
                        else (
                            self._t("interpAttention")
                            if ebitda and ebitda / receita > 0.08
                            else self._t("interpCritical")
                        )
                    ),
                }
            )

            indicators.append(
                {
                    "name": self._t("indNetMargin"),
                    "value": f"{(lucro_liquido / receita * 100):.1f}%" if lucro_liquido else "N/A",
                    "interpretation": (
                        self._t("interpHealthy")
                        if lucro_liquido and lucro_liquido / receita > 0.05
                        else (
                            self._t("interpAttention")
                            if lucro_liquido and lucro_liquido / receita > 0.02
                            else self._t("interpCritical")
                        )
                    ),
                }
            )

        return indicators

    def _calculate_structure_indicators(self, balance_data: list[dict]) -> list[dict]:
        """Calcula indicadores de estrutura do balanço."""
        # Implementação similar à DRE
        periods: dict[str, dict[str, float]] = {}
        for d in balance_data:
            if d["period"] not in periods:
                periods[d["period"]] = {}
            periods[d["period"]][d["line_item"]] = d["value"]

        latest = max(periods.keys()) if periods else None
        if not latest:
            return []

        data = periods[latest]

        ativo_circ = data.get("ativo_circulante", 0)
        passivo_circ = data.get("passivo_circulante", 0)
        patrimonio = data.get("patrimonio_liquido", 0)

        indicators = []

        if passivo_circ > 0:
            lc = ativo_circ / passivo_circ
            indicators.append(
                {
                    "name": self._t("indCurrentLiquidity"),
                    "value": f"{lc:.2f}",
                    "interpretation": (
                        self._t("interpExcellent")
                        if lc > 2
                        else (
                            self._t("interpGood")
                            if lc > 1.5
                            else self._t("interpAttention") if lc > 1 else self._t("interpCritical")
                        )
                    ),
                }
            )

        if patrimonio > 0:
            # Endividamento
            pc = data.get("passivo_circulante", 0)
            pnc = data.get("passivo_nao_circulante", 0)
            endiv = (pc + pnc) / (pc + pnc + patrimonio) * 100
            indicators.append(
                {
                    "name": self._t("indDebt"),
                    "value": f"{endiv:.1f}%",
                    "interpretation": (
                        self._t("interpExcellent")
                        if endiv < 30
                        else (
                            self._t("interpGood")
                            if endiv < 50
                            else (
                                self._t("interpAttention")
                                if endiv < 70
                                else self._t("interpCritical")
                            )
                        )
                    ),
                }
            )

        return indicators

    def _get_score_color(self, score: float) -> str:
        """Retorna cor hexadecimal baseada no score."""
        if score >= 80:
            return "#16a34a"  # verde
        elif score >= 60:
            return "#3b82f6"  # azul
        elif score >= 40:
            return "#f59e0b"  # amarelo
        else:
            return "#dc2626"  # vermelho

    def _translate_trend(self, trend: str) -> str:
        """Traduz a tendência para o idioma do relatório."""
        keys = {
            "improving": "trendImproving",
            "stable": "trendStable",
            "declining": "trendDeclining",
        }
        key = keys.get(trend)
        return self._t(key) if key else trend

    def _get_status_text(self, score: float) -> str:
        """Retorna texto de status no idioma do relatório."""
        if score >= 80:
            return self._t("statusExcellent")
        elif score >= 60:
            return self._t("statusGood")
        elif score >= 40:
            return self._t("statusRegular")
        else:
            return self._t("statusCritical")

    def _format_detail(self, component_name: str, details: dict) -> str:
        """Formata detalhes para exibição na tabela."""
        if "error" in details:
            return details["error"]

        key_info = []

        if component_name == "Margem":
            key_info.append(f"{self._t('detailAvg')}: {details.get('avg_margin_pct', 0):.1f}%")
            key_info.append(
                f"{self._t('detailNegatives')}: {details.get('negative_margin_products', 0)}"
            )

        elif component_name == "Liquidez":
            key_info.append(f"LC: {details.get('liquidez_corrente', 0):.2f}")

        elif component_name == "Endividamento":
            key_info.append(f"{details.get('endividamento_pct', 0):.1f}%")

        elif component_name == "Produção":
            key_info.append(f"{self._t('detailDelays')}: {details.get('delay_rate_pct', 0):.1f}%")

        elif component_name == "Qualidade de Dados":
            key_info.append(
                f"{self._t('detailCompleteness')}: {details.get('avg_completeness', 0):.0f}%"
            )

        elif component_name == "Sazonalidade":
            key_info.append(f"CV: {details.get('coefficient_variation', 0):.2f}")

        elif component_name == "Concentração de Clientes":
            key_info.append(f"{self._t('detailTop3')}: {details.get('top3_share_pct', 0):.1f}%")

        return "; ".join(key_info) if key_info else self._t("seeDetails")


def get_pdf_service(db: Session = Depends(get_db)) -> JUNOPDFReport:
    """Factory para injeção de dependência."""
    return JUNOPDFReport(db)
