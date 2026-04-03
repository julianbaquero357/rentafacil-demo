import os
import resend

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
MAIL_FROM = os.environ.get("MAIL_FROM")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# 👉 correo fijo demo
DESTINO_DEMO = "rentafacildemo@gmail.com"


def correo_habilitado():
    return bool(RESEND_API_KEY and MAIL_FROM)


def enviar_codigo_verificacion(destinatario, codigo):
    if not correo_habilitado():
        print("Correo no habilitado, código:", codigo)
        return None

    asunto = "Código de verificación - Renta Fácil"

    html = f"""
    <div style="font-family: Arial; padding:30px;">
        <h2>Renta Fácil</h2>
        <p>Su código de verificación es:</p>
        <h1>{codigo}</h1>
        <p>Este código es válido por unos minutos.</p>
    </div>
    """

    return resend.Emails.send({
        "from": MAIL_FROM,
        "to": [DESTINO_DEMO],
        "subject": asunto,
        "html": html
    })


def enviar_notificacion_pdf(destinatario, nombre, cedula):
    if not correo_habilitado():
        return None

    asunto = "Declaración generada - Renta Fácil"

    html = f"""
    <div style="font-family: Arial; padding:30px;">
        <h2>Declaración generada</h2>
        <p>Se ha generado una declaración para:</p>
        <ul>
            <li><b>Nombre:</b> {nombre}</li>
            <li><b>Cédula:</b> {cedula}</li>
        </ul>
    </div>
    """

    return resend.Emails.send({
        "from": MAIL_FROM,
        "to": [DESTINO_DEMO],
        "subject": asunto,
        "html": html
    })
