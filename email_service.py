import os
import resend

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
MAIL_FROM = os.environ.get("MAIL_FROM")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

def correo_habilitado():
    return bool(RESEND_API_KEY and MAIL_FROM)

def enviar_codigo_verificacion(destinatario, codigo):
    if not correo_habilitado():
        return None

    asunto = "Código de verificación - Renta Fácil"

    html = f"""
    <div style="font-family: Arial, sans-serif; background:#f4f7fb; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:16px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08);">
            <div style="background:linear-gradient(135deg,#0b5ed7,#2563eb); color:white; padding:24px;">
                <h1 style="margin:0; font-size:24px;">Renta Fácil</h1>
                <p style="margin:8px 0 0; opacity:0.9;">Código de verificación</p>
            </div>
            <div style="padding:28px; color:#0f172a;">
                <p style="font-size:15px; line-height:1.7;">
                    Se ha generado un código de verificación para continuar con el acceso seguro a la información tributaria.
                </p>
                <div style="margin:24px 0; text-align:center;">
                    <div style="display:inline-block; padding:18px 28px; background:#eff6ff; border:1px solid #dbeafe; border-radius:14px; font-size:28px; font-weight:800; letter-spacing:6px; color:#1d4ed8;">
                        {codigo}
                    </div>
                </div>
                <p style="font-size:14px; color:#64748b; line-height:1.6;">
                    Si usted no solicitó este código, puede ignorar este mensaje.
                </p>
            </div>
        </div>
    </div>
    """

    return resend.Emails.send({
        "from": MAIL_FROM,
        "to": [destinatario],
        "subject": asunto,
        "html": html
    })

def enviar_notificacion_pdf(destinatario, nombre, cedula):
    if not correo_habilitado():
        return None

    asunto = "Declaración generada - Renta Fácil"

    html = f"""
    <div style="font-family: Arial, sans-serif; background:#f4f7fb; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:16px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08);">
            <div style="background:linear-gradient(135deg,#0b5ed7,#2563eb); color:white; padding:24px;">
                <h1 style="margin:0; font-size:24px;">Renta Fácil</h1>
                <p style="margin:8px 0 0; opacity:0.9;">Notificación de generación de declaración</p>
            </div>
            <div style="padding:28px; color:#0f172a;">
                <p style="font-size:15px; line-height:1.7;">
                    Se ha generado una declaración tributaria demostrativa para el siguiente contribuyente:
                </p>

                <table style="width:100%; border-collapse:collapse; margin:18px 0;">
                    <tr>
                        <td style="padding:10px; border:1px solid #e2e8f0; background:#f8fafc; font-weight:700;">Nombre</td>
                        <td style="padding:10px; border:1px solid #e2e8f0;">{nombre}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px; border:1px solid #e2e8f0; background:#f8fafc; font-weight:700;">Cédula</td>
                        <td style="padding:10px; border:1px solid #e2e8f0;">{cedula}</td>
                    </tr>
                </table>

                <p style="font-size:14px; color:#64748b; line-height:1.6;">
                    Este mensaje corresponde a una notificación automática del entorno demostrativo de Renta Fácil.
                </p>
            </div>
        </div>
    </div>
    """

    return resend.Emails.send({
        "from": MAIL_FROM,
        "to": [destinatario],
        "subject": asunto,
        "html": html
    })
