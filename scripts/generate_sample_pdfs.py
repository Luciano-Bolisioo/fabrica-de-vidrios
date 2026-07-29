"""Genera 4 PDFs de ejemplo para probar el agente de documentos."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "samples"


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleAR",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyAR",
            parent=styles["Normal"],
            fontSize=11,
            leading=15,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallAR",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.grey,
        )
    )
    return styles


def _table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.Color(0.93, 0.95, 0.98)]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def lista_precios(path: Path) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, title="Lista de precios julio 2025")
    story = [
        Paragraph("Fábrica de Vidrios — Lista de precios", styles["TitleAR"]),
        Paragraph("Vigencia: julio 2025. Precios netos por m² en pesos argentinos.", styles["BodyAR"]),
        Spacer(1, 0.4 * cm),
        _table(
            [
                ["Producto", "Espesor / tipo", "Precio m²"],
                ["Vidrio templado", "6 mm", "$ 28.500"],
                ["Vidrio templado", "8 mm", "$ 34.200"],
                ["Vidrio templado", "10 mm", "$ 41.800"],
                ["Vidrio laminado", "3+3", "$ 32.900"],
                ["Vidrio laminado", "4+4", "$ 39.500"],
                ["Vidrio laminado", "5+5 con PVB", "$ 48.700"],
                ["DVH", "4/9/4", "$ 52.000"],
                ["DVH", "4/12/4", "$ 57.800"],
                ["Espejo", "4 mm", "$ 22.400"],
            ],
            col_widths=[6 * cm, 5 * cm, 4 * cm],
        ),
        Spacer(1, 0.6 * cm),
        Paragraph(
            "Notas: precios sin IVA. Corte a medida sin cargo hasta 10 piezas. "
            "Colocación no incluida. Consultar descuentos por volumen.",
            styles["BodyAR"],
        ),
        Paragraph("Documento de ejemplo para pruebas internas.", styles["SmallAR"]),
    ]
    doc.build(story)


def ficha_cliente(path: Path) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, title="Ficha cliente Cristalería Norte")
    story = [
        Paragraph("Ficha de cliente — Cristalería Norte S.A.", styles["TitleAR"]),
        Paragraph("<b>Razón social:</b> Cristalería Norte S.A.", styles["BodyAR"]),
        Paragraph("<b>CUIT:</b> 30-71234567-8", styles["BodyAR"]),
        Paragraph("<b>Domicilio:</b> Av. San Martín 2450, San Isidro, Buenos Aires", styles["BodyAR"]),
        Paragraph("<b>Contacto comercial:</b> Juan Pérez — jperez@cristalnorte.com.ar — 11 4567-8901", styles["BodyAR"]),
        Spacer(1, 0.3 * cm),
        Paragraph("<b>Condiciones comerciales</b>", styles["Heading2"]),
        Paragraph("Condición de pago: <b>30 días fecha factura</b>.", styles["BodyAR"]),
        Paragraph("Descuento por volumen: <b>5%</b> a partir de $ 2.000.000 (neto mensual).", styles["BodyAR"]),
        Paragraph("Límite de crédito sugerido: $ 5.000.000.", styles["BodyAR"]),
        Paragraph("Productos habituales: laminado 4+4, DVH 4/12/4, templado 8 mm.", styles["BodyAR"]),
        Spacer(1, 0.4 * cm),
        Paragraph(
            "Observaciones: cliente desde 2019. Buena puntualidad de pago. "
            "Prefiere retiros en planta los martes y jueves.",
            styles["BodyAR"],
        ),
        Paragraph("Documento de ejemplo para pruebas internas.", styles["SmallAR"]),
    ]
    doc.build(story)


def resumen_ventas(path: Path) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, title="Resumen de ventas junio 2025")
    story = [
        Paragraph("Resumen de ventas — junio 2025", styles["TitleAR"]),
        Paragraph("Fábrica de Vidrios. Totales netos (sin IVA).", styles["BodyAR"]),
        Spacer(1, 0.3 * cm),
        _table(
            [
                ["Cliente", "m² vendidos", "Monto neto"],
                ["Vidrios del Sur", "420", "$ 18.650.000"],
                ["Cristalería Norte S.A.", "310", "$ 12.480.000"],
                ["Vidriería Palermo", "185", "$ 7.215.000"],
                ["Obra Belgrano (particular)", "64", "$ 3.920.000"],
                ["Otros", "95", "$ 3.410.000"],
            ],
            col_widths=[7 * cm, 4 * cm, 4 * cm],
        ),
        Spacer(1, 0.5 * cm),
        Paragraph("<b>Total m²:</b> 1.074", styles["BodyAR"]),
        Paragraph("<b>Total neto junio:</b> $ 45.675.000", styles["BodyAR"]),
        Paragraph(
            "Producto más vendido del mes: laminado 4+4 (38% del volumen). "
            "Segundo: DVH 4/12/4 (22%).",
            styles["BodyAR"],
        ),
        Paragraph("Documento de ejemplo para pruebas internas.", styles["SmallAR"]),
    ]
    doc.build(story)


def presupuesto_belgrano(path: Path) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, title="Presupuesto obra Belgrano")
    story = [
        Paragraph("Presupuesto de obra — Belgrano", styles["TitleAR"]),
        Paragraph("<b>Cliente:</b> María Laura Gómez (particular)", styles["BodyAR"]),
        Paragraph("<b>Obra:</b> Cabrera 2850, Belgrano, CABA", styles["BodyAR"]),
        Paragraph("<b>Fecha:</b> 12/06/2025 — <b>Validez:</b> 15 días", styles["BodyAR"]),
        Spacer(1, 0.3 * cm),
        _table(
            [
                ["Ítem", "Detalle", "Cant.", "Importe"],
                ["1", "DVH 4/12/4 cocina (aperturas)", "12 m²", "$ 693.600"],
                ["2", "Laminado 4+4 barandas", "8 m²", "$ 316.000"],
                ["3", "Templado 8 mm mampara", "3 m²", "$ 102.600"],
                ["4", "Colocación y sellado", "global", "$ 280.000"],
                ["5", "Herrajes y burletes", "global", "$ 95.000"],
            ],
            col_widths=[1.5 * cm, 8 * cm, 2.5 * cm, 3 * cm],
        ),
        Spacer(1, 0.5 * cm),
        Paragraph("<b>Subtotal:</b> $ 1.487.200", styles["BodyAR"]),
        Paragraph("<b>IVA 21%:</b> $ 312.312", styles["BodyAR"]),
        Paragraph("<b>Total:</b> $ 1.799.512", styles["BodyAR"]),
        Paragraph(
            "Incluye medición en obra (1 visita). No incluye andamiaje especial. "
            "Pago: 50% anticipo, 50% contra entrega.",
            styles["BodyAR"],
        ),
        Paragraph("Documento de ejemplo para pruebas internas.", styles["SmallAR"]),
    ]
    doc.build(story)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        (OUT_DIR / "lista_precios_julio.pdf", lista_precios),
        (OUT_DIR / "ficha_cliente_cristaleria_norte.pdf", ficha_cliente),
        (OUT_DIR / "resumen_ventas_junio.pdf", resumen_ventas),
        (OUT_DIR / "presupuesto_obra_belgrano.pdf", presupuesto_belgrano),
    ]
    for path, builder in outputs:
        builder(path)
        print(f"OK {path}")


if __name__ == "__main__":
    main()
