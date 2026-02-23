import io
import uuid
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.graphics.barcode import code128
from reportlab.platypus import Image
from reportlab.lib.utils import ImageReader
from reportlab.platypus import PageBreak
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

def watermark(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 60)
    canvas.setFillColorRGB(0.9, 0.9, 0.9)
    canvas.rotate(45)
    canvas.drawCentredString(300, 0, "RENTA FÁCIL DEMO")
    canvas.restoreState()

def generar_pdf_declaracion(data):

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    cedula = data["cedula"]
    nombre = data["nombre"]
    correo = data.get("correo", "no-disponible@demo.co")
    ingresos = float(data["ingresos"])
    gastos = float(data["gastos"])
    base = float(data["base"])
    patrimonio = float(data.get("patrimonio", 0))
    deudas = float(data.get("deudas", 0))
    transacciones = data.get("transacciones", [])

    impuesto = impuesto_art241(base)

    now = datetime.datetime.now()
    anio = 2025
    numero_formulario = f"210-DEMO-{now.strftime('%H%M%S')}"
    codigo_unico = str(uuid.uuid4()).upper()[:14]

    # ESTILO
    style = ParagraphStyle(name='Normal', fontSize=10)

    # ENCABEZADO
    header_data = [
        ["RENTA FÁCIL", "", f"Año Gravable {anio}"],
        ["Declaración de renta y complementario", "", f"Formulario No. {numero_formulario}"],
        ["Personas Naturales - DEMO", "", f"Código: {codigo_unico}"]
    ]

    header_table = Table(header_data, colWidths=[250, 50, 200])
    header_table.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('SPAN', (0,1), (1,1)),
        ('SPAN', (0,2), (1,2)),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#003B73")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 10))

    # DATOS CONTRIBUYENTE
    datos_data = [
        ["Identificación", cedula],
        ["Nombre completo", nombre],
        ["Correo", correo],
        ["Fecha generación", now.strftime("%Y-%m-%d %H:%M")]
    ]

    datos_table = Table(datos_data, colWidths=[200, 300])
    datos_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#EAEFF5"))
    ]))

    elements.append(datos_table)
    elements.append(Spacer(1, 15))

    # TABLA TIPO 210
    tabla_data = [
        ["Casilla", "Concepto", "Valor"]
    ]

    filas = [
        ("32", "Ingresos brutos", fmt(ingresos)),
        ("42", "Deducciones", fmt(gastos)),
        ("43", "Renta líquida", fmt(base)),
        ("95", "Impuesto neto de renta", fmt(impuesto))
    ]

    tabla_data.extend(filas)

    tabla = Table(tabla_data, colWidths=[80, 300, 120])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#003B73")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (2,1), (-1,-1), 'RIGHT')
    ]))

    elements.append(tabla)
    elements.append(Spacer(1, 20))

    # PATRIMONIO
    patrimonio_data = [
        ["Patrimonio bruto", fmt(patrimonio)],
        ["Deudas", fmt(deudas)],
        ["Patrimonio líquido", fmt(max(0, patrimonio - deudas))]
    ]

    patrimonio_table = Table(patrimonio_data, colWidths=[250, 250])
    patrimonio_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#EAEFF5"))
    ]))

    elements.append(patrimonio_table)
    elements.append(PageBreak())

    # SEGUNDA PÁGINA - DETALLE
    detalle_data = [["ID", "Tipo", "Valor"]]

    for t in transacciones[:25]:
        detalle_data.append([
            t.get("id_transaccion"),
            t.get("tipo"),
            fmt(t.get("valor"))
        ])

    detalle_table = Table(detalle_data, colWidths=[150, 150, 150])
    detalle_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#003B73")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white)
    ]))

    elements.append(detalle_table)
    elements.append(Spacer(1, 30))

    # CÓDIGO DE BARRAS
    barcode = code128.Code128(numero_formulario, barHeight=40)
    elements.append(barcode)

    # QR
    qr = qrcode.make(f"{cedula}|{numero_formulario}|{anio}")
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_img = Image(qr_buffer, width=60, height=60)
    elements.append(Spacer(1, 10))
    elements.append(qr_img)

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "Documento generado electrónicamente por Renta Fácil (DEMO). "
        "Firma digital institucional simulada.",
        style
    ))

    doc.build(elements, onFirstPage=watermark, onLaterPages=watermark)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf
