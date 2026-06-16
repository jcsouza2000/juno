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


class JUNOPDFReport:
    """
    Gerador de relatórios PDF executivos.
    """

    def __init__(self, db: Session):
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

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

    def generate_executive_report(self, company_id: int) -> bytes:
        """
        Gera relatório executivo completo em PDF.
        """
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
        story.append(Paragraph("Relatório Executivo", self.styles["JUNO_Section"]))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(f"<b>Empresa:</b> {company.name}", self.styles["JUNO_Body"]))
        story.append(Paragraph(f"<b>Setor:</b> {company.sector}", self.styles["JUNO_Body"]))
        story.append(
            Paragraph(
                f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                self.styles["JUNO_Body"],
            )
        )
        story.append(Spacer(1, 2 * cm))

        # Score JUNO
        score_color = self._get_score_color(score_result.overall_score)
        story.append(Paragraph(f"{score_result.overall_score:.0f}", self.styles["JUNO_Score"]))
        story.append(Paragraph("Score JUNO", self.styles["JUNO_ScoreLabel"]))
        story.append(
            Paragraph(
                f"Tendência: {self._translate_trend(score_result.trend)} ({score_result.trend_delta:+.1f})",
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
                f"<font size='14' color='{score_color}'>{trend_arrow} Score {score_result.trend}</font>",
                self.styles["JUNO_ScoreLabel"],
            )
        )

        story.append(PageBreak())

        # ============================================================
        # COMPONENTES DO SCORE
        # ============================================================
        story.append(Paragraph("Análise por Componentes", self.styles["JUNO_Section"]))
        story.append(Spacer(1, 0.5 * cm))

        # Tabela de componentes
        comp_data = [["Componente", "Peso", "Score", "Status", "Detalhes"]]
        for comp in score_result.components:
            status = self._get_status_text(comp.normalized_score)
            detail_text = self._format_detail(comp.name, comp.details)
            comp_data.append(
                [
                    comp.name,
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
        story.append(Paragraph("Recomendações Executivas", self.styles["JUNO_Section"]))
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
        # DEMONSTRAÇÕES FINANCEIRAS
        # ============================================================
        self._add_financial_statements(story, company_id)

        story.append(PageBreak())

        # ============================================================
        # RODAPÉ
        # ============================================================
        story.append(
            Paragraph(
                f"<font size='8' color='grey'>JUNO Industrial Diagnostic v2.0 | Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
                f"Este relatório é confidencial e destinado exclusivamente à gestão da {company.name}.</font>",
                self.styles["JUNO_ScoreLabel"],
            )
        )

        # Build PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def _add_financial_statements(self, story: list, company_id: int):
        """Adiciona DRE, Balanço e DFC ao relatório."""
        if templates_financeiro and templates_financeiro.use_templates_as_canonical():
            relatorio = templates_financeiro.build_demonstracoes_relatorio()
            if relatorio:
                self._add_template_report(story, relatorio)
                return

        # DRE
        story.append(
            Paragraph("Demonstração do Resultado do Exercício (DRE)", self.styles["JUNO_Section"])
        )

        dre_data = self._get_dre_data(company_id)
        if dre_data:
            dre_table = self._create_financial_table(dre_data, "DRE")
            story.append(dre_table)
            story.append(Spacer(1, 0.5 * cm))

            # Indicadores DRE
            indicators = self._calculate_dre_indicators(dre_data)
            ind_data = [["Indicador", "Valor", "Interpretação"]]
            for ind in indicators:
                ind_data.append([ind["name"], ind["value"], ind["interpretation"]])

            ind_table = Table(ind_data, colWidths=[5 * cm, 3 * cm, 8 * cm])
            ind_table.setStyle(self._get_indicator_table_style())
            story.append(ind_table)
        else:
            story.append(
                Paragraph(
                    "DRE não disponível. Faça upload em /financials.", self.styles["JUNO_Alert"]
                )
            )

        story.append(Spacer(1, 1 * cm))

        # Balanço
        story.append(Paragraph("Balanço Patrimonial", self.styles["JUNO_Section"]))

        balance_data = self._get_balance_data(company_id)
        if balance_data:
            bal_table = self._create_financial_table(balance_data, "Balanco")
            story.append(bal_table)
            story.append(Spacer(1, 0.5 * cm))

            # Indicadores de estrutura
            structure = self._calculate_structure_indicators(balance_data)
            struct_data = [["Indicador", "Valor", "Interpretação"]]
            for s in structure:
                struct_data.append([s["name"], s["value"], s["interpretation"]])

            struct_table = Table(struct_data, colWidths=[5 * cm, 3 * cm, 8 * cm])
            struct_table.setStyle(self._get_indicator_table_style())
            story.append(struct_table)
        else:
            story.append(
                Paragraph(
                    "Balanço não disponível. Faça upload em /financials.", self.styles["JUNO_Alert"]
                )
            )

        story.append(Spacer(1, 1 * cm))

        # DFC
        story.append(Paragraph("Demonstração de Fluxo de Caixa (DFC)", self.styles["JUNO_Section"]))

        dfc_data = self._get_dfc_data(company_id)
        if dfc_data:
            dfc_table = self._create_financial_table(dfc_data, "DFC")
            story.append(dfc_table)
        else:
            story.append(
                Paragraph(
                    "DFC não disponível. Faça upload em /financials.", self.styles["JUNO_Alert"]
                )
            )

    def _add_template_report(self, story: list, relatorio: dict) -> None:
        """Renderiza demonstrações no layout do modelo Templates."""
        story.append(
            Paragraph(
                f"{relatorio.get('titulo', 'Demonstrações Financeiras')} "
                f"({relatorio.get('unidade', 'R$ milhões')})",
                self.styles["JUNO_Section"],
            )
        )
        story.append(
            Paragraph(
                f"Fonte: {relatorio.get('fonte', 'Templates')} · "
                f"DRE/DFC {relatorio.get('competencia', '')} · "
                f"Balanço {relatorio.get('patrimonial', '')}",
                self.styles["JUNO_Body"],
            )
        )
        story.append(Spacer(1, 0.4 * cm))

        for secao in relatorio.get("secoes", []):
            story.append(Paragraph(secao.get("titulo", "Seção"), self.styles["JUNO_SubSection"]))
            table = self._create_template_table(secao)
            story.append(table)
            story.append(Spacer(1, 0.5 * cm))

    def _create_template_table(self, secao: dict) -> Table:
        periodos = secao.get("periodos") or []
        header = ["Conta", *periodos]
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
                FinancialStatement.statement_type == "Balanco",
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
        header = ["Conta"] + periods

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
                    "name": "Margem Bruta",
                    "value": f"{(lucro_bruto / receita * 100):.1f}%",
                    "interpretation": (
                        "Saudável"
                        if lucro_bruto / receita > 0.3
                        else "Atenção" if lucro_bruto / receita > 0.15 else "Crítico"
                    ),
                }
            )

            indicators.append(
                {
                    "name": "Margem EBITDA",
                    "value": f"{(ebitda / receita * 100):.1f}%" if ebitda else "N/A",
                    "interpretation": (
                        "Saudável"
                        if ebitda and ebitda / receita > 0.15
                        else "Atenção" if ebitda and ebitda / receita > 0.08 else "Crítico"
                    ),
                }
            )

            indicators.append(
                {
                    "name": "Margem Líquida",
                    "value": f"{(lucro_liquido / receita * 100):.1f}%" if lucro_liquido else "N/A",
                    "interpretation": (
                        "Saudável"
                        if lucro_liquido and lucro_liquido / receita > 0.05
                        else (
                            "Atenção"
                            if lucro_liquido and lucro_liquido / receita > 0.02
                            else "Crítico"
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
                    "name": "Liquidez Corrente",
                    "value": f"{lc:.2f}",
                    "interpretation": (
                        "Excelente"
                        if lc > 2
                        else "Bom" if lc > 1.5 else "Atenção" if lc > 1 else "Crítico"
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
                    "name": "Endividamento",
                    "value": f"{endiv:.1f}%",
                    "interpretation": (
                        "Excelente"
                        if endiv < 30
                        else "Bom" if endiv < 50 else "Atenção" if endiv < 70 else "Crítico"
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
        """Traduz tendência para português."""
        translations = {"improving": "Melhorando", "stable": "Estável", "declining": "Piorando"}
        return translations.get(trend, trend)

    def _get_status_text(self, score: float) -> str:
        """Retorna texto de status."""
        if score >= 80:
            return "Excelente"
        elif score >= 60:
            return "Bom"
        elif score >= 40:
            return "Regular"
        else:
            return "Crítico"

    def _format_detail(self, component_name: str, details: dict) -> str:
        """Formata detalhes para exibição na tabela."""
        if "error" in details:
            return details["error"]

        key_info = []

        if component_name == "Margem":
            key_info.append(f"Média: {details.get('avg_margin_pct', 0):.1f}%")
            key_info.append(f"Negativos: {details.get('negative_margin_products', 0)}")

        elif component_name == "Liquidez":
            key_info.append(f"LC: {details.get('liquidez_corrente', 0):.2f}")

        elif component_name == "Endividamento":
            key_info.append(f"{details.get('endividamento_pct', 0):.1f}%")

        elif component_name == "Produção":
            key_info.append(f"Atrasos: {details.get('delay_rate_pct', 0):.1f}%")

        elif component_name == "Qualidade de Dados":
            key_info.append(f"Completude: {details.get('avg_completeness', 0):.0f}%")

        elif component_name == "Sazonalidade":
            key_info.append(f"CV: {details.get('coefficient_variation', 0):.2f}")

        elif component_name == "Concentração de Clientes":
            key_info.append(f"Top3: {details.get('top3_share_pct', 0):.1f}%")

        return "; ".join(key_info) if key_info else "Ver detalhes"


def get_pdf_service(db: Session = Depends(get_db)) -> JUNOPDFReport:
    """Factory para injeção de dependência."""
    return JUNOPDFReport(db)
