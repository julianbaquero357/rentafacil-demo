import io
import uuid
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode import code128
import qrcode

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
    return f"${float(x):,.0f}".replace(",", ".")

def clasificar_ingresos(transacciones):
    laboral = 0
    no_laboral = 0
    capital = 0

    for t in transacciones:
        if t["tipo"] != "ingreso":
            continue

        desc = (t.get("descripcion") or "").lower()

        if "salario" in desc:
            laboral += float(t["valor"])
        elif "honorario" in desc:
            no_laboral += float(t["valor"])
        elif "interes" in desc:
            capital += float(t["valor"])
        else:
            laboral += float(t["valor"])

    return laboral, no_laboral, capital

def generar_pdf_declaracion(data):

    cedula = data["cedula"]
    nombre = data["nombre"]
    ingresos = float(data["ingresos"])
    gastos = float(data["gastos"])
    base = float(data["base"])
    patrimonio = float(data.get("patrimonio", 0))
    deudas = float(data.get("deudas", 0))
    transacciones = data.get("transacciones", [])

    impuesto = impuesto_art241(base)

    laboral, no_laboral, capital = clasificar_ingresos(transacciones)

    now = datetime.datetime.now()
    anio = 2025
    numero_formulario = f"RF210-{now.strftime('%H%M%S')}"
    codigo_unico = str(uuid.uuid4()).upper()[:16]

    qr_data = f"{cedula}|{numero_formulario}|{anio}"
    qr = qrcode.make(qr_data)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_img = ImageReader(qr_buffer)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    W, H = letter
    margin = 20 * mm

    # ENCABEZADO
    c.setFillColor(colors.HexColor("#003B73"))
    c.rect(0, H - 60, W, 60, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, H - 35, "RENTA FÁCIL")
    c.setFont("Helvetica", 9)
    c.drawString(margin, H - 50,
                 "FORMATO 210 - DEMO | Declaración de renta personas naturales")

    y = H - 80

    # DATOS GENERALES
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)

    c.drawString(margin, y, f"Año gravable: {anio}")
    c.drawString(margin, y - 15, f"Número formulario: {numero_formulario}")
    c.drawString(margin, y - 30, f"Código único: {codigo_unico}")
    c.drawRightString(W - margin, y,
                      f"Fecha: {now.strftime('%Y-%m-%d %H:%M')}")

    # Código barras
    barcode = code128.Code128(numero_formulario, barHeight=20)
    barcode.drawOn(c, margin, y - 60)

    # Casillas tipo 210
    y -= 100
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Resumen Cedular")

    y -= 15
    c.setFont("Helvetica", 9)

    filas = [
        ("32", "Ingresos laborales", laboral),
        ("33", "Ingresos no laborales", no_laboral),
        ("34", "Ingresos de capital", capital),
        ("41", "Total ingresos", ingresos),
        ("42", "Total deducciones", gastos),
        ("43", "Renta líquida", base),
        ("95", "Impuesto neto de renta", impuesto)
    ]

    for casilla, concepto, valor in filas:
        c.drawString(margin, y, casilla)
        c.drawString(margin + 40, y, concepto)
        c.drawRightString(W - margin, y, fmt(valor))
        y -= 15

    # Segunda página
    c.showPage()

    # Página 2
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, H - 40, "Detalle resumido de transacciones")

    y = H - 60
    c.setFont("Helvetica", 8)

    for t in transacciones[:20]:
        c.drawString(margin, y,
                     f"{t.get('id_transaccion')} | {t.get('tipo')} | {fmt(t.get('valor'))}")
        y -= 12
        if y < 80:
            break

    # QR grande
    c.drawImage(qr_img, W - margin - 80, 100, width=70, height=70)

    c.line(margin, 90, W - margin, 90)
    c.setFont("Helvetica", 8)
    c.drawString(margin, 75,
                 "Documento generado electrónicamente por Renta Fácil (DEMO).")
    c.drawString(margin, 62,
                 f"Firma digital institucional simulada | Verificación: {codigo_unico}")

    c.drawRightString(W - margin, 20, "Página 2 de 2")

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
