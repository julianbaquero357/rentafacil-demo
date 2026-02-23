from sheets_sync import sync_transacciones
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

from flask import Flask, render_template, request, session, redirect
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
import os
import gspread
import json
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = "clave_demo_rentafacil"

# ===============================
# SCHEDULER (actualiza cada minuto)
# ===============================
scheduler = BackgroundScheduler()
scheduler.add_job(func=sync_transacciones, trigger="interval", seconds=60)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ===============================
# CONFIGURACIÓN CORREO DEMO
# ===============================
EMAIL = "rentafacildemo@gmail.com"
PASSWORD = "ujky bszn wpaj jckv"

def enviar_codigo(correo, codigo):
    try:
        msg = MIMEText(f"Su código de verificación es: {codigo}")
        msg["Subject"] = "Código de verificación - Renta Fácil"
        msg["From"] = EMAIL
        msg["To"] = correo

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(EMAIL, PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print("No se pudo enviar el correo:", e)
        print("Código demo:", codigo)

# ===============================
# CONEXIÓN GOOGLE SHEETS
# ===============================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def conectar_google():
    sa_json = json.loads(os.environ["GOOGLE_SA_JSON"])
    creds = Credentials.from_service_account_info(sa_json, scopes=SCOPES)
    return gspread.authorize(creds)

# ===============================
# CÁLCULO DE RENTA DESDE HISTORIAL
# ===============================
def calcular_renta(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    historial_ws = sheet.worksheet("historial")

    registros = historial_ws.get_all_records()

    ingresos = 0
    gastos = 0

    for r in registros:
        if str(r["cedula"]).strip() == str(cedula):
            if r["tipo"] == "ingreso":
                ingresos += float(r["valor"])
            elif r["tipo"] == "gasto":
                gastos += float(r["valor"])

    base = ingresos - gastos
    impuesto = base * 0.10 if base > 0 else 0

    # Buscar nombre en pestaña usuarios
    usuarios_ws = sheet.worksheet("usuarios")
    usuarios = usuarios_ws.get_all_records()

    nombre = "Contribuyente"
    for u in usuarios:
        if str(u["cedula"]).strip() == str(cedula):
            nombre = u["nombre"]
            break

    return {
        "nombre": nombre,
        "ingresos": ingresos,
        "gastos": gastos,
        "base": base,
        "impuesto": impuesto
    }

# ===============================
# RUTAS
# ===============================

@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/consultar", methods=["POST"])
def consultar():
    cedula = request.form["cedula"]

    # Validar que exista en Google Sheet usuarios
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios_ws = sheet.worksheet("usuarios")
    usuarios = usuarios_ws.get_all_records()

    existe = any(str(u["cedula"]).strip() == cedula for u in usuarios)

    if not existe:
        return "Usuario no encontrado"

    codigo = str(random.randint(100000, 999999))
    session["codigo"] = codigo
    session["cedula"] = cedula

    enviar_codigo(EMAIL, codigo)

    return render_template("verificar.html", codigo_demo=codigo)


@app.route("/verificar", methods=["POST"])
def verificar():
    codigo_usuario = request.form["codigo"]

    if codigo_usuario != session.get("codigo"):
        return "Código incorrecto"

    cedula = session.get("cedula")
    resultado = calcular_renta(cedula)

    return render_template("resultado.html", data=resultado)


# ===============================
# SYNC MANUAL ADMIN
# ===============================
@app.route("/admin/sync", methods=["POST"])
def admin_sync():
    nuevos = sync_transacciones()
    return {"nuevos_registros": nuevos}


# ===============================
# EJECUCIÓN
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
