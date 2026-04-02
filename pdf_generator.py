import io
import uuid
import datetime
import qrcode

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode import code128

UVT_2025 = 49799


def impuesto_art241(base):
    base_uvt = max(0, base / UVT_2025)

    tramos = [
        (0, 1090, 0.00, 0),
        (1090, 1700, 0.19, 0),
        (1700, 4100, 0.28, 116),
        (4100, 8670, 0.33, 788),
        (8670, 18970, 0.35, 2296),
        (18970, 31000, 0.37, 5901),
        (31000, float("inf"), 0.39, 10352),
    ]

    for desde, hasta, tarifa, fijo in tramos:
        if base_uvt > desde and base_uvt <= hasta:
            impuesto_uvt = (base_uvt - desde) * tarifa + fijo
            return round(impuesto_uvt * UVT_2025)

    return 0


def fmt(x):
    try:
        return f"${float(x):,.0f}".replace(",", ".")
    except:
        return "$0"


def clasificar_ingresos(transacciones):
    laboral = 0
    no_laboral = 0
    capital = 0

    for t in transacciones:
        if t.get("tipo") != "ingreso":
            continue

        desc = str(t.get("descripcion", "")).lower()

        if "salario" in desc or "nomina" in desc:
            laboral += float(t.get("valor", 0))
        elif "honorario" in desc or "servicio" in desc:
            no_laboral += float(t.get("valor", 0))
        elif "interes" in desc or "rendimiento" in desc:
            capital += float(t.get("valor", 0))
        else:
            laboral += float(t.get("valor", 0))

    return laboral, no_laboral, capital


def draw_watermark(c, w, h):
    c.saveState()
    c.setFont("Helvetica-Bold", 52)
    c.setFillColor(colors.Color(0.92, 0.94, 0.97, alpha=1))
    c.translate(w / 2, h / 2)
    c.rotate(38)
    c.drawCentredString(0, 0, "RENTA FÁCIL DEMO")
    c.restoreState()


def draw_header(c, w, h, margin, anio, numero_formulario, codigo_unico, fecha_generacion):
    c.setFillColor(colors.HexColor("#0B3D91"))
    c.rect(0, h - 58, w, 58, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, h - 28, "RENTA FÁCIL")
    c.setFont("Helvetica", 9)
    c.drawString(margin, h - 43, "FORMATO 210 - DEMO | Declaración de renta y complementario")

    # Caja derecha tipo formulario
    box_w = 145
    box_h = 42
    x_box = w - margin - box_w
    y_box = h - 49

    c.setFillColor(colors.white)
    c.roundRect(x_box, y_box, box_w, box_h, 6, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_box + 8, y_box + 28, "AÑO GRAVABLE")
    c.drawRightString(x_box + box_w - 8, y_box + 28, str(anio))

    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_box + 8, y_box + 14, "FORMULARIO")
    c.drawRightString(x_box + box_w - 8, y_box + 14, numero_formulario)

    # Línea separadora inferior
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.line(margin, h - 72, w - margin, h - 72)

    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica", 8)
    c.drawString(margin, h - 84, f"Código único de declaración: {codigo_unico}")
    c.drawRightString(w - margin, h - 84, f"Fecha de generación: {fecha_generacion}")


def draw_data_box(c, x, y, w, h, title, rows):
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.setFillColor(colors.white)
    c.roundRect(x, y - h, w, h, 8, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#EAF1FB"))
    c.roundRect(x, y - 24, w, 24, 8, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 10, y - 16, title)

    c.setFont("Helvetica", 8.5)
    row_y = y - 38
    for label, value in rows:
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(x + 10, row_y, str(label))
        c.setFillColor(colors.HexColor("#0F172A"))
        c.drawString(x + 115, row_y, str(value))
        row_y -= 14


def draw_form_table(c, x, y, col_widths, rows, row_height=18):
    total_w = sum(col_widths)

    # Header
    c.setFillColor(colors.HexColor("#0B3D91"))
    c.rect(x, y - row_height, total_w, row_height, fill=1, stroke=0)

    cx = x
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.white)
    for i, txt in enumerate(rows[0]):
        c.drawCentredString(cx + col_widths[i] / 2, y - 12, str(txt))
        cx += col_widths[i]

    # Grid rows
    cy = y - row_height
    c.setFont("Helvetica", 8)
    for row in rows[1:]:
        cy -= row_height
        c.setFillColor(colors.white)
        c.rect(x, cy, total_w, row_height, fill=1, stroke=0)

        cx = x
        for i, txt in enumerate(row):
            c.setStrokeColor(colors.HexColor("#CBD5E1"))
            c.rect(cx, cy, col_widths[i], row_height, fill=0, stroke=1)

            if i == len(row) - 1:
                c.setFillColor(colors.HexColor("#0F172A"))
                c.drawRightString(cx + col_widths[i] - 6, cy + 6, str(txt))
            else:
                c.setFillColor(colors.HexColor("#0F172A"))
                c.drawString(cx + 6, cy + 6, str(txt))

            cx += col_widths[i]

    return cy


def generar_pdf_declaracion(data):
    cedula = str(data.get("cedula", "")).strip()
    nombre = str(data.get("nombre", "Contribuyente")).strip()
    correo = str(data.get("correo", "no-disponible@demo.co")).strip()

    ingresos = float(data.get("ingresos", 0) or 0)
    gastos = float(data.get("gastos", 0) or 0)
    base = float(data.get("base", 0) or 0)
    patrimonio = float(data.get("patrimonio", 0) or 0)
    deudas = float(data.get("deudas", 0) or 0)
    transacciones = data.get("transacciones", []) or []

    impuesto = impuesto_art241(base)
    patrimonio_liquido = max(0, patrimonio - deudas)

    ingresos_laborales, ingresos_no_laborales, ingresos_capital = clasificar_ingresos(transacciones)

    now = datetime.datetime.now()
    fecha_generacion = now.strftime("%Y-%m-%d %H:%M")
    anio = 2025
    numero_formulario = f"RF210-{now.strftime('%H%M%S')}"
    codigo_unico = str(uuid.uuid4()).upper()[:16]

    qr_data = f"RF|{cedula}|{numero_formulario}|{anio}|{codigo_unico}"
    qr = qrcode.make(qr_data)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_img = ImageReader(qr_buffer)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    margin = 18 * mm

    # PÁGINA 1
    draw_watermark(c, w, h)
    draw_header(c, w, h, margin, anio, numero_formulario, codigo_unico, fecha_generacion)

    # Código de barras
    barcode = code128.Code128(numero_formulario, barHeight=18, barWidth=0.6)
    barcode.drawOn(c, margin, h - 118)

    # QR arriba derecha, separado
    c.drawImage(qr_img, w - margin - 52, h - 150, width=44, height=44)

    # Datos del contribuyente
    top_y = h - 155
    draw_data_box(
        c,
        margin,
        top_y,
        w - 2 * margin,
        72,
        "Datos del contribuyente",
        [
            ("Identificación", cedula),
            ("Nombre completo", nombre),
            ("Correo", correo),
        ]
    )

    # Bloques de patrimonio e identificación tributaria
    left_x = margin
    right_x = w / 2 + 6
    block_y = top_y - 88

    draw_data_box(
        c,
        left_x,
        block_y,
        (w / 2) - margin - 6,
        68,
        "Patrimonio",
        [
            ("Patrimonio bruto", fmt(patrimonio)),
            ("Deudas", fmt(deudas)),
            ("Patrimonio líquido", fmt(patrimonio_liquido)),
        ]
    )

    draw_data_box(
        c,
        right_x,
        block_y,
        (w / 2) - margin - 6,
        68,
        "Identificación del formulario",
        [
            ("Año gravable", anio),
            ("Formulario", numero_formulario),
            ("Código único", codigo_unico),
        ]
    )

    # Tabla principal estilo formulario
    table_y = block_y - 86
    rows = [
        ["Casilla", "Concepto", "Valor"],
        ["32", "Ingresos laborales", fmt(ingresos_laborales)],
        ["33", "Ingresos no laborales", fmt(ingresos_no_laborales)],
        ["34", "Ingresos de capital", fmt(ingresos_capital)],
        ["41", "Total ingresos brutos", fmt(ingresos)],
        ["42", "Deducciones / costos", fmt(gastos)],
        ["43", "Renta líquida gravable", fmt(base)],
        ["95", "Impuesto neto de renta (Art. 241 E.T.)", fmt(impuesto)],
    ]

    col_widths = [52, 320, 120]
    end_y = draw_form_table(c, margin, table_y, col_widths, rows, row_height=21)

    # Caja final resumen
    final_y = end_y - 24
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.roundRect(margin, final_y - 54, w - 2 * margin, 54, 8, fill=1, stroke=1)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(margin + 12, final_y - 18, "Resultado estimado de la declaración")
    c.setFont("Helvetica", 9)
    c.drawString(margin + 12, final_y - 34, f"Base gravable estimada: {fmt(base)}")
    c.drawRightString(w - margin - 12, final_y - 34, f"Impuesto proyectado: {fmt(impuesto)}")

    # Pie página 1
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.line(margin, 52, w - margin, 52)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(margin, 38, "Documento generado electrónicamente por Renta Fácil (DEMO).")
    c.drawRightString(w - margin, 38, "Página 1 de 2")

    c.showPage()

    # PÁGINA 2
    draw_watermark(c, w, h)
    draw_header(c, w, h, margin, anio, numero_formulario, codigo_unico, fecha_generacion)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(margin, h - 112, "Detalle resumido de transacciones registradas")

    tx_rows = [["ID", "Tipo", "Descripción", "Valor"]]
    for t in transacciones[:22]:
        tx_rows.append([
            str(t.get("id_transaccion", "")),
            str(t.get("tipo", "")),
            str(t.get("descripcion", ""))[:38],
            fmt(t.get("valor", 0))
        ])

    tx_col_widths = [86, 72, 270, 92]
    tx_end_y = draw_form_table(c, margin, h - 126, tx_col_widths, tx_rows, row_height=19)

    # QR + barcode inferior
    c.drawImage(qr_img, margin, 86, width=62, height=62)
    barcode2 = code128.Code128(numero_formulario, barHeight=26, barWidth=0.7)
    barcode2.drawOn(c, margin + 85, 98)

    # Firma institucional simulada
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.line(margin, 72, w - margin, 72)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(margin, 56, "Firma digital institucional simulada")
    c.setFont("Helvetica", 8)
    c.drawString(margin, 44, f"Verificación: {codigo_unico}")
    c.drawRightString(w - margin, 38, "Página 2 de 2")

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
