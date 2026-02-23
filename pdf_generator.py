import io
import uuid
import datetime
from typing import List, Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from reportlab.graphics.barcode import code128

import qrcode

UVT_2025 = 49799  # COP

# -------------------------
# Impuesto Art. 241 (UVT)
# -------------------------
def impuesto_art241_pesos(base_gravable_pesos: float) -> Dict[str, Any]:
    base_uvt = max(0.0, base_gravable_pesos / UVT_2025)

    # Tabla marginal (Art. 241 E.T.)
    tramos = [
        (0, 1090, 0.00, 0),
        (1090, 1700, 0.19, 0),
        (1700, 4100, 0.28, 116),
        (4100, 8670, 0.33, 788),
        (8670, 18970, 0.35, 2296),
        (18970, 31000, 0.37, 5901),
        (31000, float("inf"), 0.39, 10352),
    ]

    for desde, hasta, tarifa, fijo_uvt in tramos:
        if base_uvt > desde and base_uvt <= hasta:
            impuesto_uvt = (base_uvt - desde) * tarifa + fijo_uvt
            impuesto_cop = round(impuesto_uvt * UVT_2025)
            return {
                "base_uvt": base_uvt,
                "desde_uvt": desde,
                "hasta_uvt": hasta,
                "tarifa": tarifa,
                "fijo_uvt": fijo_uvt,
                "impuesto_uvt": impuesto_uvt,
                "impuesto_cop": impuesto_cop
            }

    return {
        "base_uvt": base_uvt,
        "desde_uvt": 0,
        "hasta_uvt": 1090,
        "tarifa": 0.0,
        "fijo_uvt": 0,
        "impuesto_uvt": 0,
        "impuesto_cop": 0
    }

def _fmt_money(x) -> str:
    try:
        return f"${float(x):,.0f}".replace(",", ".")
    except:
        return "$0"

def _safe_float(x) -> float:
    try:
        return float(x)
    except:
        return 0.0

def _upper(s) -> str:
    return (s or "").strip().upper()

# ------------------------------------------------------
# Clasificación simple por descripción (DEMO)
# ------------------------------------------------------
def clasificar_ingreso(descripcion: str) -> str:
    d = _upper(descripcion)
    # Laborales
    if any(k in d for k in ["SALARIO", "NOMINA", "NÓMINA", "PAGO EMPLEO", "SUELDO", "HONORARIOS"]):
        return "laboral"
    # Capital
    if any(k in d for k in ["INTERES", "INTERÉS", "RENDIMIENTO", "DIVIDENDO", "ARRENDAMIENTO", "ALQUILER"]):
        return "capital"
    # No laborales
    if any(k in d for k in ["VENTA", "SERVICIO", "TRANSFERENCIA", "PSE", "EFECTY", "NEQUI", "DAVIPLATA"]):
        return "no_laboral"
    # Por defecto
    return "no_laboral"

def clasificar_gasto(descripcion: str) -> str:
    d = _upper(descripcion)
    # Solo para separar (opcional)
    if any(k in d for k in ["MERCADO", "SUPERMERCADO", "ALIMENTO", "COMIDA"]):
        return "consumo"
    if any(k in d for k in ["ARRIENDO", "ALQUILER"]):
        return "vivienda"
    if any(k in d for k in ["SALUD", "EPS", "MEDICO", "MÉDICO", "FARMACIA"]):
        return "salud"
    return "gasto_general"

# ------------------------------------------------------
# Dibujos utilitarios
# ------------------------------------------------------
def _draw_header(c: canvas.Canvas, W, H, margin, anio, form_no, codigo_unico, fecha_str, qr_reader, barcode_value):
    # Franja superior
    c.setFillColor(colors.HexColor("#003B73"))
    c.rect(0, H - 62, W, 62, fill=1, stroke=0)
    c.setFillColor(colors.white)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, H - 34, "RENTA FÁCIL")
    c.setFont("Helvetica", 9)
    c.drawString(margin, H - 50, "FORMATO 210 - DEMO | Declaración de renta y complementario (Personas Naturales)")

    # Caja superior (2 columnas + QR)
    top_y = H - 78
    box_h = 68
    box_w = W - 2 * margin
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#B0B8C1"))
    c.rect(margin, top_y - box_h, box_w, box_h, fill=0, stroke=1)

    # Columna izquierda
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(margin + 10, top_y - 18, f"Año gravable: {anio}")
    c.drawString(margin + 10, top_y - 34, f"Número formulario: {form_no}")
    c.drawString(margin + 10, top_y - 50, f"Código único: {codigo_unico}")

    # Columna derecha (fecha alineada)
    c.drawRightString(W - margin - 90, top_y - 18, f"Fecha generación: {fecha_str}")

    # QR (en su propia zona, sin tapar)
    c.drawImage(qr_reader, W - margin - 70, top_y - 62, width=56, height=56, mask="auto")

    # Código de barras (debajo del header, completo)
    bar = code128.Code128(barcode_value, barHeight=12 * mm, barWidth=0.45)
    bar_x = margin
    bar_y = top_y - box_h - 16 * mm
    bar.drawOn(c, bar_x, bar_y)
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawString(margin, bar_y - 10, f"Código de barras (DEMO): {barcode_value}")

    return bar_y - 22  # retorna y inicial para continuar

def _draw_footer(c: canvas.Canvas, W, margin, page, total_pages, codigo_unico):
    c.setStrokeColor(colors.HexColor("#B0B8C1"))
    c.line(margin, 85, W - margin, 85)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#2B2B2B"))
    c.drawString(margin, 70, "Documento generado electrónicamente por Renta Fácil (DEMO).")
    c.drawString(margin, 58, f"Firma digital institucional simulada | Verificación: {codigo_unico}")
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawString(margin, 46, "Este documento es una demostración técnica y no constituye un formulario oficial de la DIAN.")

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#2B2B2B"))
    c.drawRightString(W - margin, 62, f"Página {page} de {total_pages}")
    c.drawRightString(W - margin, 50, "Formulario 210 - DEMO | Año gravable 2025")

def _draw_section_title(c, x, y, title):
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#003B73"))
    c.drawString(x, y, title)
    c.setFillColor(colors.black)

def _draw_box(c, x, y, w, h):
    c.setStrokeColor(colors.HexColor("#B0B8C1"))
    c.rect(x, y - h, w, h, fill=0, stroke=1)

def _draw_casilla_table(c, x, y, w, rows):
    """
    rows: list of tuples (casilla, concepto, valor_str)
    """
    row_h = 14
    h = row_h * (len(rows) + 1)
    _draw_box(c, x, y, w, h)

    # header
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.rect(x, y - row_h, w, row_h, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#1F2937"))
    c.drawString(x + 8, y - 10, "Casilla")
    c.drawString(x + 70, y - 10, "Concepto")
    c.drawRightString(x + w - 8, y - 10, "Valor (COP)")

    # lines
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    for i in range(len(rows) + 1):
        yy = y - row_h * (i + 1)
        c.line(x, yy, x + w, yy)

    # content
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    for i, (casilla, concepto, valor) in enumerate(rows):
        yy = y - row_h * (i + 1) - 10
        c.drawString(x + 8, yy, str(casilla))
        c.drawString(x + 70, yy, str(concepto))
        c.drawRightString(x + w - 8, yy, str(valor))

    return y - h - 14

def _paginate_transacciones(transacciones: List[Dict[str, Any]], max_rows=20):
    pages = []
    for i in range(0, len(transacciones), max_rows):
        pages.append(transacciones[i:i + max_rows])
    return pages

def _draw_transacciones_table(c, x, y, w, trans, title="Detalle de transacciones (DEMO)"):
    _draw_section_title(c, x, y, title)
    y -= 10

    row_h = 14
    # header + rows
    h = row_h * (len(trans) + 1)
    _draw_box(c, x, y, w, h)

    # header
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.rect(x, y - row_h, w, row_h, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#1F2937"))
    c.drawString(x + 8, y - 10, "ID")
    c.drawString(x + 85, y - 10, "Tipo")
    c.drawString(x + 135, y - 10, "Descripción")
    c.drawRightString(x + w - 8, y - 10, "Valor")

    # content
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)

    # grid lines
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    for i in range(len(trans) + 1):
        yy = y - row_h * (i + 1)
        c.line(x, yy, x + w, yy)

    for i, t in enumerate(trans):
        yy = y - row_h * (i + 1) - 10
        tid = str(t.get("id_transaccion", ""))[:12]
        tipo = str(t.get("tipo", ""))[:10]
        desc = str(t.get("descripcion", ""))[:42]
        val = _fmt_money(_safe_float(t.get("valor", 0)))

        c.drawString(x + 8, yy, tid)
        c.drawString(x + 85, yy, tipo)
        c.drawString(x + 135, yy, desc)
        c.drawRightString(x + w - 8, yy, val)

    return y - h - 14

# ------------------------------------------------------
# GENERADOR PRINCIPAL
# ------------------------------------------------------
def generar_pdf_declaracion(data: Dict[str, Any]) -> bytes:
    cedula = str(data.get("cedula", "")).strip()
    nombre = str(data.get("nombre", "CONTRIBUYENTE")).strip()

    anio = 2025
    now = datetime.datetime.now()
    fecha_str = now.strftime("%Y-%m-%d %H:%M")

    ingresos_total = _safe_float(data.get("ingresos", 0))
    gastos_total = _safe_float(data.get("gastos", 0))
    base = _safe_float(data.get("base", ingresos_total - gastos_total))

    patrimonio = _safe_float(data.get("patrimonio", 0))
    deudas = _safe_float(data.get("deudas", 0))
    patrimonio_liquido = max(0.0, patrimonio - deudas)

    transacciones = data.get("transacciones") or []
    if not isinstance(transacciones, list):
        transacciones = []

    # Clasificación ingresos por descripción (DEMO)
    ingresos_laborales = 0.0
    ingresos_no_laborales = 0.0
    ingresos_capital = 0.0

    for t in transacciones:
        if str(t.get("tipo", "")).lower() == "ingreso":
            desc = str(t.get("descripcion", "") or "")
            cat = clasificar_ingreso(desc)
            v = _safe_float(t.get("valor", 0))
            if cat == "laboral":
                ingresos_laborales += v
            elif cat == "capital":
                ingresos_capital += v
            else:
                ingresos_no_laborales += v

    # Si no hay detalle, todo se asume "no_laboral"
    if (ingresos_laborales + ingresos_no_laborales + ingresos_capital) == 0 and ingresos_total > 0:
        ingresos_no_laborales = ingresos_total

    # Impuesto Art. 241
    calc = impuesto_art241_pesos(base)
    impuesto = calc["impuesto_cop"]

    # IDs
    consecutivo = now.strftime("%m%d%H%M%S")
    form_no = f"RF-210-{anio}-{consecutivo}"
    codigo_unico = f"{str(uuid.uuid4()).upper().split('-')[0]}-{str(uuid.uuid4()).upper().split('-')[1]}-{anio}"

    barcode_value = f"{anio}{cedula}{consecutivo}"[:28]  # límite razonable para Code128

    # QR
    qr_payload = f"RENTA_FACIL|FORM:{form_no}|CC:{cedula}|ANIO:{anio}|COD:{codigo_unico}"
    qr_img = qrcode.make(qr_payload)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_reader = ImageReader(qr_buf)

    # ¿2 páginas?
    # Página 1: resumen + casillas
    # Página 2: detalle transacciones (si hay muchas)
    trans_pages = _paginate_transacciones(transacciones, max_rows=20)
    needs_second_page = len(transacciones) > 12  # umbral para “se vea pro” (p2)
    total_pages = 2 if needs_second_page else 1

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter
    margin = 14 * mm

    # =======================
    # PÁGINA 1
    # =======================
    y = _draw_header(c, W, H, margin, anio, form_no, codigo_unico, fecha_str, qr_reader, barcode_value)

    # Datos contribuyente
    _draw_section_title(c, margin, y, "Datos del contribuyente")
    y -= 10
    _draw_box(c, margin, y, W - 2 * margin, 45)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    c.drawString(margin + 10, y - 18, f"5. Identificación (C.C.): {cedula}")
    c.drawString(margin + 10, y - 32, f"9. Nombre completo: {nombre}")
    y -= 65

    # Patrimonio
    _draw_section_title(c, margin, y, "Patrimonio (DEMO)")
    y -= 10
    _draw_box(c, margin, y, W - 2 * margin, 55)
    c.setFont("Helvetica", 9)
    c.drawString(margin + 10, y - 18, f"29. Patrimonio bruto: {_fmt_money(patrimonio)}")
    c.drawString(margin + 10, y - 35, f"30. Deudas: {_fmt_money(deudas)}")
    c.drawRightString(W - margin - 10, y - 18, f"31. Patrimonio líquido: {_fmt_money(patrimonio_liquido)}")
    y -= 75

    # Tabla “casillas” (tipo 210 DEMO)
    _draw_section_title(c, margin, y, "Resumen cedular y liquidación (DEMO)")
    y -= 12

    rows = [
        (32, "Ingresos brutos (total)", _fmt_money(ingresos_total)),
        (32.1, "Ingresos laborales (estimado)", _fmt_money(ingresos_laborales)),
        (32.2, "Ingresos no laborales (estimado)", _fmt_money(ingresos_no_laborales)),
        (32.3, "Ingresos de capital (estimado)", _fmt_money(ingresos_capital)),
        (34, "Costos/Gastos deducibles (registrados)", _fmt_money(gastos_total)),
        (42, "Base gravable estimada", _fmt_money(base)),
        (95, "Base gravable (UVT)", f"{calc['base_uvt']:.2f}"),
        (96, "Tramo UVT (desde - hasta)", f"{calc['desde_uvt']} - {('∞' if calc['hasta_uvt'] == float('inf') else int(calc['hasta_uvt']))}"),
        (97, "Tarifa marginal aplicable", f"{int(calc['tarifa']*100)}%"),
        (98, "Impuesto fijo del tramo (UVT)", f"{calc['fijo_uvt']}"),
        (126, "Impuesto neto de renta (estimado)", _fmt_money(impuesto)),
        (980, "Pago total (DEMO)", _fmt_money(impuesto)),
    ]

    y = _draw_casilla_table(c, margin, y, W - 2 * margin, rows)

    # Nota de firma / paginación
    _draw_footer(c, W, margin, page=1, total_pages=total_pages, codigo_unico=codigo_unico)
    c.showPage()

    # =======================
    # PÁGINA 2 (opcional)
    # =======================
    if needs_second_page:
        # Header más compacto en p2
        c.setFillColor(colors.HexColor("#003B73"))
        c.rect(0, H - 50, W, 50, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, H - 30, "RENTA FÁCIL | Anexo de movimientos (DEMO)")
        c.setFont("Helvetica", 9)
        c.drawString(margin, H - 42, f"Formulario: {form_no}  |  C.C.: {cedula}  |  Año: {anio}")

        y2 = H - 70

        # Tabla de transacciones (si hay muchas, se muestra 1 página; para demo, basta)
        # Si quisieras más de 2 páginas reales, se puede extender.
        page_trans = trans_pages[0] if trans_pages else []
        y2 = _draw_transacciones_table(c, margin, y2, W - 2 * margin, page_trans)

        # Si hay más de 20 transacciones, mostramos aviso (sin romper demo)
        if len(trans_pages) > 1:
            c.setFont("Helvetica-Oblique", 8)
            c.setFillColor(colors.HexColor("#666666"))
            c.drawString(margin, y2, f"Nota: Se omitieron {len(transacciones) - len(page_trans)} movimientos adicionales por límite de la demostración.")

        _draw_footer(c, W, margin, page=2, total_pages=total_pages, codigo_unico=codigo_unico)
        c.showPage()

    c.save()
    out = buf.getvalue()
    buf.close()
    return out
