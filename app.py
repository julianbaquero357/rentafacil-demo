from flask import Flask, render_template, request, session, redirect, send_file
from functools import wraps
import os
import json
import random
import sqlite3
import time
import smtplib
import io
from email.mime.text import MIMEText

import gspread
from google.oauth2.service_account import Credentials

from sheets_sync import sync_transacciones
from pdf_generator import generar_pdf_declaracion

app = Flask(__name__)
app.secret_key = "clave_demo_rentafacil"

# =====================================================
# CONFIGURACIÓN CORREO DEMO
# =====================================================
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
        print("Correo no enviado:", e)
        print("Código demo:", codigo)

# =====================================================
# GOOGLE SHEETS
# =====================================================
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

# =====================================================
# AUTO SYNC
# =====================================================
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
        return

    try:
        sync_transacciones()
        cur.execute("INSERT OR REPLACE INTO sync_state (k, v) VALUES ('last_sync_ts', ?)", (str(now),))
        conn.commit()
    except Exception as e:
        print("Error sync:", e)

    conn.close()

# =====================================================
# LOGIN ADMIN
# =====================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        if usuario == "admin" and password == "admin":
            session["admin_logged"] = True
            return redirect("/admin")
        else:
            return render_template("admin_login.html", error="Credenciales incorrectas")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect("/admin/login")

# =====================================================
# CÁLCULO RENTA
# =====================================================
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
            nombre = u.get("nombre", "Contribuyente")
            break

    for r in historial:
        if normalizar_cedula(r["cedula"]) == cedula:
            if r["tipo"] == "ingreso":
                ingresos += float(r["valor"])
            elif r["tipo"] == "gasto":
                gastos += float(r["valor"])

    base = ingresos - gastos

    return {
        "nombre": nombre,
        "ingresos": ingresos,
        "gastos": gastos,
        "base": base
    }

# =====================================================
# RUTAS
# =====================================================
@app.route("/")
def inicio():
    maybe_sync()
    return render_template("index.html")

@app.route("/admin")
@login_required
def admin_panel():
    maybe_sync()

    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios = sheet.worksheet("usuarios").get_all_records()
    historial = sheet.worksheet("historial").get_all_records()

    total_ingresos = sum(float(r["valor"]) for r in historial if r["tipo"] == "ingreso")
    total_gastos = sum(float(r["valor"]) for r in historial if r["tipo"] == "gasto")
    total_base = total_ingresos - total_gastos

    return render_template("admin.html",
                           total_usuarios=len(usuarios),
                           total_ingresos=total_ingresos,
                           total_gastos=total_gastos,
                           total_base=total_base)

@app.route("/admin/usuario", methods=["POST"])
@login_required
def admin_usuario():
    cedula = request.form["cedula"]
    cedula = normalizar_cedula(cedula)

    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios = sheet.worksheet("usuarios").get_all_records()
    historial = sheet.worksheet("historial").get_all_records()

    nombre = "No encontrado"
    patrimonio = 0
    deudas = 0

    for u in usuarios:
        if normalizar_cedula(u["cedula"]) == cedula:
            nombre = u.get("nombre", "Contribuyente")
            patrimonio = float(u.get("patrimonio", 0) or 0)
            deudas = float(u.get("deudas", 0) or 0)
            break

    transacciones = []
    ingresos = 0
    gastos = 0

    for r in historial:
        if normalizar_cedula(r["cedula"]) == cedula:
            transacciones.append(r)
            if r["tipo"] == "ingreso":
                ingresos += float(r["valor"])
            elif r["tipo"] == "gasto":
                gastos += float(r["valor"])

    base = ingresos - gastos

    return render_template("admin_usuario.html",
                           nombre=nombre,
                           cedula=cedula,
                           ingresos=ingresos,
                           gastos=gastos,
                           base=base,
                           patrimonio=patrimonio,
                           deudas=deudas,
                           transacciones=transacciones)

@app.route("/admin/pdf/<cedula>")
@login_required
def admin_pdf(cedula):
    cedula = normalizar_cedula(cedula)
    resultado = calcular_renta(cedula)

    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios = sheet.worksheet("usuarios").get_all_records()

    patrimonio = 0
    deudas = 0

    for u in usuarios:
        if normalizar_cedula(u["cedula"]) == cedula:
            patrimonio = float(u.get("patrimonio", 0) or 0)
            deudas = float(u.get("deudas", 0) or 0)
            break

    data_pdf = {
        "cedula": cedula,
        "nombre": resultado["nombre"],
        "ingresos": resultado["ingresos"],
        "gastos": resultado["gastos"],
        "base": resultado["base"],
        "patrimonio": patrimonio,
        "deudas": deudas
    }

    pdf_bytes = generar_pdf_declaracion(data_pdf)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Declaracion_RentaFacil_210_DEMO_{cedula}_AG2025.pdf"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
