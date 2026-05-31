"""
JUNO Export Engine
Exportação de relatórios para PDF, Excel, CSV e JSON
"""

import json
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from openpyxl.styles import Alignment, Font, PatternFill

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


class ExportEngine:
    """
    Engine de exportação de relatórios.

    Formatos suportados:
    - PDF: Relatórios formatados com tabelas e gráficos
    - Excel: Planilhas com formatação e gráficos embutidos
    - CSV: Dados brutos para importação
    - JSON: Dados estruturados para integração
    """

    def __init__(self):
        self.exports_dir = "exports"
        os.makedirs(self.exports_dir, exist_ok=True)

    def export(
        self,
        data: list[dict],
        columns: list[dict],
        format: str,
        title: str = "Relatório",
        subtitle: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Exporta dados para o formato especificado.

        Returns:
            Dict com file_path, file_size, mime_type
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{title.replace(' ', '_')}_{timestamp}"

        file_path = os.path.join(self.exports_dir, f"{filename}.{format}")

        try:
            if format == "pdf":
                return self._export_pdf(data, columns, title, subtitle, file_path)
            elif format == "excel":
                return self._export_excel(data, columns, title, file_path)
            elif format == "csv":
                return self._export_csv(data, columns, file_path)
            elif format == "json":
                return self._export_json(data, columns, file_path)
            else:
                raise ValueError(f"Formato não suportado: {format}")

        except Exception as e:
            logger.error(f"[EXPORT] Erro ao exportar {format}: {str(e)}")
            raise

    def _export_pdf(
        self,
        data: list[dict],
        columns: list[dict],
        title: str,
        subtitle: str | None,
        file_path: str,
    ) -> dict[str, Any]:
        """Exporta para PDF usando ReportLab."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab não está instalado. Instale com: pip install reportlab")

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        story = []

        # Título
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#1a237e"),
            spaceAfter=12,
        )
        story.append(Paragraph(title, title_style))

        # Subtítulo
        if subtitle:
            story.append(Paragraph(subtitle, styles["Normal"]))
            story.append(Spacer(1, 0.5 * cm))

        # Data de geração
        story.append(
            Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"])
        )
        story.append(Spacer(1, 1 * cm))

        # Tabela de dados
        if data:
            # Preparar headers
            headers = [col.get("label", col["field"]) for col in columns]

            # Preparar rows
            rows = [headers]
            for row in data[:1000]:  # Limitar a 1000 linhas para PDF
                rows.append(
                    [
                        str(row.get(col["field"], ""))[:50]  # Truncar strings longas
                        for col in columns
                    ]
                )

            # Criar tabela
            table = Table(rows, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 1), (-1, -1), 9),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )

            story.append(table)
        else:
            story.append(Paragraph("Nenhum dado encontrado.", styles["Normal"]))

        # Rodapé
        story.append(Spacer(1, 1 * cm))
        story.append(
            Paragraph("JUNO ERP Intelligence — Relatório gerado automaticamente", styles["Italic"])
        )

        doc.build(story)

        return {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "mime_type": "application/pdf",
            "format": "pdf",
        }

    def _export_excel(
        self, data: list[dict], columns: list[dict], title: str, file_path: str
    ) -> dict[str, Any]:
        """Exporta para Excel com formatação."""
        if not OPENPYXL_AVAILABLE:
            raise ImportError("OpenPyXL não está instalado. Instale com: pip install openpyxl")

        df = pd.DataFrame(data)

        # Reordenar colunas conforme config
        col_fields = [c["field"] for c in columns if c["field"] in df.columns]
        if col_fields:
            df = df[col_fields]

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            # Aba principal
            df.to_excel(writer, sheet_name="Dados", index=False)

            # Aba de resumo
            summary_data = {
                "Métrica": ["Total de Registros", "Data de Geração", "Título"],
                "Valor": [len(data), datetime.now().strftime("%d/%m/%Y %H:%M"), title],
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Resumo", index=False)

            # Formatar aba de dados
            worksheet = writer.sheets["Dados"]

            # Header style
            header_fill = PatternFill(start_color="1a237e", end_color="1a237e", fill_type="solid")
            header_font = Font(color="FFFFFF", bold=True)

            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            # Auto-ajustar larguras
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except (TypeError, ValueError):
                        continue
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

            # Congelar header
            worksheet.freeze_panes = "A2"

        return {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "format": "excel",
        }

    def _export_csv(self, data: list[dict], columns: list[dict], file_path: str) -> dict[str, Any]:
        """Exporta para CSV."""
        df = pd.DataFrame(data)
        col_fields = [c["field"] for c in columns if c["field"] in df.columns]
        if col_fields:
            df = df[col_fields]

        df.to_csv(file_path, index=False, encoding="utf-8-sig")

        return {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "mime_type": "text/csv",
            "format": "csv",
        }

    def _export_json(self, data: list[dict], columns: list[dict], file_path: str) -> dict[str, Any]:
        """Exporta para JSON estruturado."""
        export_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "record_count": len(data),
                "columns": columns,
            },
            "data": data,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

        return {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "mime_type": "application/json",
            "format": "json",
        }

    def generate_chart_image(
        self, data: list[dict], chart_type: str, x_field: str, y_field: str, title: str = "Gráfico"
    ) -> bytes | None:
        """Gera imagem de gráfico para embed em PDF/dashboard."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        df = pd.DataFrame(data)

        if x_field not in df.columns or y_field not in df.columns:
            return None

        plt.figure(figsize=(10, 6))

        if chart_type == "bar":
            df.plot(kind="bar", x=x_field, y=y_field, legend=False)
        elif chart_type == "line":
            df.plot(kind="line", x=x_field, y=y_field, marker="o", legend=False)
        elif chart_type == "pie":
            df.groupby(x_field)[y_field].sum().plot(kind="pie", autopct="%1.1f%%")
        elif chart_type == "area":
            df.plot(kind="area", x=x_field, y=y_field, alpha=0.5, legend=False)

        plt.title(title)
        plt.xlabel(x_field.replace("_", " ").title())
        plt.ylabel(y_field.replace("_", " ").title())
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
        plt.close()

        return buffer.getvalue()
