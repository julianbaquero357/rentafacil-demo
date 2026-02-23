import io
import uuid
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import qrcode

UVT_2025 = 49799

def impuesto_art241_pesos(base):
    base_uvt = max(0.0, base / UVT_2025)

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
            return round(impuesto_uvt * UVT_2025)

    return 0

def fmt(x):
    return f"${float(x):,.0f}".replace(",", ".")

def generar_pdf_declaracion(data):

    cedula = data["cedula"]
    nombre = data["nombre"]
    ingresos = float(data["ingresos"])
    gastos = float(data["gastos"])
    base = float(data["base"])
    patrimonio = float(data.get("patrimonio", 0))
    deudas = float(data.get("deudas", 0))

    impuesto = impuesto_art241_pesos(base)

    now = datetime.datetime.now()
    anio = 2025
    numero_formulario = f"RF-210-{anio}-{now.strftime('%H%M%S')}"
    codigo_unico = str(uuid.uuid4()).upper()[:12]

    # Generar QR
    qr_data = f"RF|{cedula}|{numero_formulario}|{anio}"
    qr = qrcode.make(qr_data)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_img = ImageReader(qr_buffer)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    W, H = letter

    margin = 20 * mm

    # Encabezado
    c.setFillColor(colors.HexColor("#003B73"))
    c.rect(0, H - 60, W, 60, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, H - 35, "RENTA FÁCIL")
    c.setFont("Helvetica", 9)
    c.drawString(margin, H - 50,
                 "FORMATO 210 - DEMO | Declaración de renta y complementario (Personas Naturales)")

    y = H - 80

    # Datos generales caja
    c.setStrokeColor(colors.grey)
    c.rect(margin, y - 60, W - 2*margin, 60)

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)

    c.drawString(margin + 10, y - 20, f"Año gravable: {anio}")
    c.drawString(margin + 10, y - 35, f"Número formulario: {numero_formulario}")
    c.drawString(margin + 10, y - 50, f"Código único: {codigo_unico}")

    c.drawRightString(W - margin - 10, y - 20,
                      f"Fecha generación: {now.strftime('%Y-%m-%d %H:%M')}")

    # QR separado claramente
    c.drawImage(qr_img, W - margin - 70, y - 55, width=50, height=50)

    y -= 90

    # Datos contribuyente
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Datos del contribuyente")
    y -= 10
    c.rect(margin, y - 45, W - 2*margin, 45)

    c.setFont("Helvetica", 9)
    c.drawString(margin + 10, y - 18, f"Identificación (C.C.): {cedula}")
    c.drawString(margin + 10, y - 32, f"Nombre completo: {nombre}")

    y -= 70

    # Patrimonio
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Patrimonio (DEMO)")
    y -= 10
    c.rect(margin, y - 45, W - 2*margin, 45)

    c.setFont("Helvetica", 9)
    c.drawString(margin + 10, y - 18, f"Patrimonio bruto: {fmt(patrimonio)}")
    c.drawString(margin + 10, y - 32, f"Deudas: {fmt(deudas)}")
    c.drawRightString(W - margin - 10, y - 18,
                      f"Patrimonio líquido: {fmt(max(0, patrimonio - deudas))}")

    y -= 70

    # Resumen renta
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Resumen renta")
    y -= 10
    c.rect(margin, y - 80, W - 2*margin, 80)

    c.setFont("Helvetica", 9)
    c.drawString(margin + 10, y - 18, f"Ingresos brutos: {fmt(ingresos)}")
    c.drawString(margin + 10, y - 32, f"Gastos deducibles: {fmt(gastos)}")
    c.drawString(margin + 10, y - 46, f"Base gravable: {fmt(base)}")
    c.drawRightString(W - margin - 10, y - 18,
                      f"Impuesto estimado (Art. 241 E.T.): {fmt(impuesto)}")

    # Pie institucional
    c.line(margin, 90, W - margin, 90)
    c.setFont("Helvetica", 8)
    c.drawString(margin, 75,
                 "Documento generado electrónicamente por Renta Fácil (DEMO).")
    c.drawString(margin, 62,
                 f"Firma digital institucional simulada | Verificación: {codigo_unico}")
    c.setFont("Helvetica-Oblique", 7)
    c.drawString(margin, 50,
                 "Este documento es una demostración técnica y no constituye un formulario oficial de la DIAN.")

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
