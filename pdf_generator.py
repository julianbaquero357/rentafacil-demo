import io
import uuid
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

import qrcode

UVT_2025 = 49799  # COP, DIAN Resolución 000193 de 2024

def impuesto_art241_pesos(base_gravable_pesos: float) -> dict:
    """
    Implementación demo basada en Art. 241 E.T. (tabla UVT).
    Devuelve impuesto en COP y detalles del tramo.
    """
    base_uvt = max(0.0, base_gravable_pesos / UVT_2025)

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
                "tramo_desde_uvt": desde,
                "tramo_hasta_uvt": hasta,
                "tarifa": tarifa,
                "fijo_uvt": fijo_uvt,
                "impuesto_uvt": impuesto_uvt,
                "impuesto_cop": impuesto_cop
            }

    return {
        "base_uvt": base_uvt,
        "tramo_desde_uvt": 0,
        "tramo_hasta_uvt": 1090,
        "tarifa": 0.0,
        "fijo_uvt": 0,
        "impuesto_uvt": 0,
        "impuesto_cop": 0
    }

def _fmt_money(x):
    try:
        return f"${float(x):,.0f}".replace(",", ".")
    except:
        return "$0"

def generar_pdf_declaracion(data: dict) -> bytes:
    """
    data esperado:
      - cedula, nombre
      - patrimonio, deudas (opcionales)
      - ingresos, gastos, base
      - impuesto (opcional; si no viene, se calcula con art 241)
      - transacciones (lista opcional) para resumen
    """
    cedula = str(data.get("cedula", "")).strip()
    nombre = str(data.get("nombre", "CONTRIBUYENTE")).strip()
    anio = 2025

    ingresos = float(data.get("ingresos", 0) or 0)
    gastos = float(data.get("gastos", 0) or 0)
    base = float(data.get("base", ingresos - gastos) or 0)

    patrimonio = float(data.get("patrimonio", 0) or 0)
    deudas = float(data.get("deudas", 0) or 0)

    calc = impuesto_art241_pesos(base)
    impuesto = float(data.get("impuesto", calc["impuesto_cop"]) or 0)

    # IDs tipo “formulario”
    now = datetime.datetime.now()
    consecutivo = now.strftime("%m%d%H%M%S")
    numero_formulario = f"RF-210-{anio}-{consecutivo}"
    codigo_unico = str(uuid.uuid4()).upper().split("-")
    codigo_unico = f"{codigo_unico[0]}-{codigo_unico[1]}-{anio}"

    # QR (contiene info resumida)
    qr_payload = f"RENTA_FACIL|FORM:{numero_formulario}|CC:{cedula}|ANIO:{anio}|COD:{codigo_unico}"
    qr_img = qrcode.make(qr_payload)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_reader = ImageReader(qr_buf)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    # Márgenes
    mx = 14 * mm
    my = 14 * mm

    # Encabezado institucional (DEMO)
    c.setFillColor(colors.HexColor("#003B73"))
    c.rect(0, H - 60, W, 60, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(mx, H - 35, "RENTA FÁCIL")
    c.setFont("Helvetica", 10)
    c.drawString(mx, H - 50, "FORMATO 210 - DEMO | Declaración de renta y complementario (Personas Naturales)")

    # Caja datos generales
    y = H - 80
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mx, y, "Datos generales")
    y -= 8
    c.setStrokeColor(colors.HexColor("#B0B8C1"))
    c.rect(mx, y - 70, W - 2*mx, 70, fill=0, stroke=1)

    c.setFont("Helvetica", 10)
    c.drawString(mx + 8, y - 18, f"Año gravable: {anio}")
    c.drawString(mx + 8, y - 35, f"Número de formulario: {numero_formulario}")
    c.drawString(mx + 8, y - 52, f"Código único de declaración: {codigo_unico}")
    c.drawRightString(W - mx - 8, y - 18, f"Fecha generación: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # QR
    c.drawImage(qr_reader, W - mx - 70, y - 65, width=60, height=60, mask="auto")

    # Datos contribuyente
    y -= 90
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mx, y, "Datos del contribuyente")
    y -= 8
    c.rect(mx, y - 60, W - 2*mx, 60, fill=0, stroke=1)
    c.setFont("Helvetica", 10)
    c.drawString(mx + 8, y - 20, f"Identificación (C.C.): {cedula}")
    c.drawString(mx + 8, y - 40, f"Nombre completo: {nombre}")

    # Patrimonio / deudas
    y -= 80
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mx, y, "Patrimonio")
    y -= 8
    c.rect(mx, y - 55, W - 2*mx, 55, fill=0, stroke=1)
    c.setFont("Helvetica", 10)
    c.drawString(mx + 8, y - 20, f"Patrimonio bruto (DEMO): {_fmt_money(patrimonio)}")
    c.drawString(mx + 8, y - 38, f"Deudas (DEMO): {_fmt_money(deudas)}")
    c.drawRightString(W - mx - 8, y - 20, f"Patrimonio líquido (DEMO): {_fmt_money(max(0, patrimonio - deudas))}")

    # Resumen cedular / renta
    y -= 75
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mx, y, "Resumen renta (DEMO)")
    y -= 8
    c.rect(mx, y - 90, W - 2*mx, 90, fill=0, stroke=1)
    c.setFont("Helvetica", 10)
    c.drawString(mx + 8, y - 22, f"Ingresos brutos (registrados): {_fmt_money(ingresos)}")
    c.drawString(mx + 8, y - 40, f"Costos/Gastos deducibles (registrados): {_fmt_money(gastos)}")
    c.drawString(mx + 8, y - 58, f"Base gravable estimada: {_fmt_money(base)}")
    c.drawRightString(W - mx - 8, y - 22, f"Base gravable (UVT): {calc['base_uvt']:.2f}")

    # Impuesto según Art. 241
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mx + 8, y - 80, "Impuesto estimado (Art. 241 E.T.)")
    c.setFont("Helvetica", 10)
    c.drawRightString(W - mx - 8, y - 80, f"{_fmt_money(impuesto)}")

    # Pie tipo “firma digital”
    y = 90
    c.setStrokeColor(colors.HexColor("#B0B8C1"))
    c.line(mx, y + 40, W - mx, y + 40)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#2B2B2B"))
    c.drawString(mx, y + 25, "Documento generado electrónicamente por Renta Fácil (DEMO).")
    c.drawString(mx, y + 12, f"Firma digital institucional simulada | Verificación: {codigo_unico}")
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.HexColor("#777777"))
    c.drawString(mx, y, "Este documento es una demostración técnica y no constituye un formulario oficial de la DIAN.")

    # “Sello” simulado
    c.setFillColor(colors.HexColor("#003B73"))
    c.circle(W - mx - 40, 70, 26, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(W - mx - 40, 70, "RF")

    c.showPage()
    c.save()

    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
