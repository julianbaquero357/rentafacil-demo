from flask import Flask, render_template, request, session
import os
import json
import random
import sqlite3
import time
import smtplib
from email.mime.text import MIMEText

import gspread
from google.oauth2.service_account import Credentials

from sheets_sync import sync_transacciones

app = Flask(__name__)
app.secret_key = "clave_demo_rentafacil"

# =========================================
# CONFIGURACIÓN CORREO DEMO
# =========================================
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

# =========================================
# GOOGLE SHEETS
# =========================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def conectar_google():
    sa_json = json.loads(os.environ["GOOGLE_SA_JSON"])
    creds = Credentials.from_service_account_info(sa_json, scopes=SCOPES)
    return gspread.authorize(creds)

def normalizar_cedula(valor):
    if valor is None:
        return ""
    try:
        return str(int(float(valor))).strip()
    except:
        return str(valor).strip()

# =========================================
# AUTO SYNC SIN SCHEDULER
# =========================================
SYNC_INTERVAL_SEC = 60

def maybe_sync():
    conn = sqlite3.connect("renta.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            k TEXT PRIMARY KEY,
            v TEXT
        )
    """)

    cur.execute("SELECT v FROM sync_state WHERE k='last_sync_ts'")
    row = cur.fetchone()
    last_ts = float(row[0]) if row and row[0] else 0

    now = time.time()
    if now - last_ts < SYNC_INTERVAL_SEC:
        conn.close()
        return {"synced": False}

    try:
        nuevos = sync_transacciones()
        cur.execute("INSERT OR REPLACE INTO sync_state (k, v) VALUES ('last_sync_ts', ?)", (str(now),))
        conn.commit()
        conn.close()
        return {"synced": True, "nuevos": nuevos}
    except Exception as e:
        conn.close()
        print("Error en sync:", e)
        return {"synced": False, "error": str(e)}

# =========================================
# VALIDAR USUARIO
# =========================================
def usuario_existe(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    ws = sheet.worksheet("usuarios")
    usuarios = ws.get_all_records()

    cedula = normalizar_cedula(cedula)
    return any(normalizar_cedula(u["cedula"]) == cedula for u in usuarios)

# =========================================
# CÁLCULO DESDE HISTORIAL
# =========================================
def calcular_renta(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    historial_ws = sheet.worksheet("historial")
    usuarios_ws = sheet.worksheet("usuarios")

    historial = historial_ws.get_all_records()
    usuarios = usuarios_ws.get_all_records()

    cedula = normalizar_cedula(cedula)

    ingresos = 0
    gastos = 0
    nombre = "Contribuyente"

    for u in usuarios:
        if normalizar_cedula(u["cedula"]) == cedula:
            nombre = u["nombre"]
            break

    for r in historial:
        if normalizar_cedula(r["cedula"]) == cedula:
            if r["tipo"] == "ingreso":
                ingresos += float(r["valor"])
            elif r["tipo"] == "gasto":
                gastos += float(r["valor"])

    base = ingresos - gastos
    impuesto = base * 0.10 if base > 0 else 0

    return {
        "nombre": nombre,
        "ingresos": ingresos,
        "gastos": gastos,
        "base": base,
        "impuesto": impuesto
    }

# =========================================
# RUTAS PÚBLICAS
# =========================================
@app.route("/")
def inicio():
    maybe_sync()
    return render_template("index.html")

@app.route("/consultar", methods=["POST"])
def consultar():
    maybe_sync()

    cedula = request.form["cedula"]

    if not usuario_existe(cedula):
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

# =========================================
# PANEL ADMINISTRADOR
# =========================================
@app.route("/admin")
def admin_panel():
    maybe_sync()

    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios_ws = sheet.worksheet("usuarios")
    historial_ws = sheet.worksheet("historial")

    usuarios = usuarios_ws.get_all_records()
    historial = historial_ws.get_all_records()

    total_ingresos = 0
    total_gastos = 0

    for r in historial:
        if r["tipo"] == "ingreso":
            total_ingresos += float(r["valor"])
        elif r["tipo"] == "gasto":
            total_gastos += float(r["valor"])

    total_base = total_ingresos - total_gastos

    return render_template("admin.html",
                           total_usuarios=len(usuarios),
                           total_ingresos=total_ingresos,
                           total_gastos=total_gastos,
                           total_base=total_base)

@app.route("/admin/usuario", methods=["POST"])
def admin_usuario():
    cedula = request.form["cedula"]

    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios_ws = sheet.worksheet("usuarios")
    historial_ws = sheet.worksheet("historial")

    usuarios = usuarios_ws.get_all_records()
    historial = historial_ws.get_all_records()

    nombre = "No encontrado"

    for u in usuarios:
        if normalizar_cedula(u["cedula"]) == normalizar_cedula(cedula):
            nombre = u["nombre"]
            break

    transacciones = []
    ingresos = 0
    gastos = 0

    for r in historial:
        if normalizar_cedula(r["cedula"]) == normalizar_cedula(cedula):
            transacciones.append(r)
            if r["tipo"] == "ingreso":
                ingresos += float(r["valor"])
            elif r["tipo"] == "gasto":
                gastos += float(r["valor"])

    base = ingresos - gastos
    impuesto = base * 0.10 if base > 0 else 0

    return render_template("admin_usuario.html",
                           nombre=nombre,
                           cedula=cedula,
                           ingresos=ingresos,
                           gastos=gastos,
                           base=base,
                           impuesto=impuesto,
                           transacciones=transacciones)

# =========================================
# SYNC MANUAL
# =========================================
@app.route("/admin/sync")
def admin_sync():
    resultado = maybe_sync()
    return f"Sync: {resultado}"

# =========================================
# HEALTH CHECK
# =========================================
@app.route("/health")
def health():
    return {"ok": True}

# =========================================
# EJECUCIÓN
# =========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
