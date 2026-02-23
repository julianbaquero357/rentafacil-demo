from flask import Flask, render_template, request, session
import os
import json
import random
import sqlite3
import time

# Correo demo (en Render SMTP puede fallar, pero no bloqueamos flujo)
import smtplib
from email.mime.text import MIMEText

import gspread
from google.oauth2.service_account import Credentials

from sheets_sync import sync_transacciones

app = Flask(__name__)
app.secret_key = "clave_demo_rentafacil"

# ===============================
# CONFIGURACIÓN CORREO DEMO
# ===============================
EMAIL = "rentafacildemo@gmail.com"
PASSWORD = "ujky bszn wpaj jckv"  # contraseña de aplicación (demo)

def enviar_codigo(correo, codigo):
    """
    En Render puede fallar por red. Si falla, igual seguimos y mostramos código demo en pantalla.
    """
    try:
        msg = MIMEText(f"Su código de verificación es: {codigo}")
        msg["Subject"] = "Código de verificación - Renta Fácil"
        msg["From"] = EMAIL
        msg["To"] = correo

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(EMAIL, PASSWORD)
            server.send_message(msg)

        print("Correo enviado correctamente")

    except Exception as e:
        print("No se pudo enviar el correo:", e)
        print("Código demo:", codigo)

# ===============================
# GOOGLE SHEETS
# ===============================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def conectar_google():
    sa_json = json.loads(os.environ["GOOGLE_SA_JSON"])
    creds = Credentials.from_service_account_info(sa_json, scopes=SCOPES)
    return gspread.authorize(creds)

def usuario_existe_en_sheet(cedula: str) -> bool:
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    ws = sheet.worksheet("usuarios")
    usuarios = ws.get_all_records()
    cedula = str(cedula).strip()
    return any(str(u.get("cedula", "")).strip() == cedula for u in usuarios)

def calcular_renta_desde_historial(cedula: str):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    historial_ws = sheet.worksheet("historial")

    registros = historial_ws.get_all_records()

    ingresos = 0.0
    gastos = 0.0
    cedula = str(cedula).strip()

    for r in registros:
        if str(r.get("cedula", "")).strip() != cedula:
            continue
        tipo = str(r.get("tipo", "")).strip().lower()
        valor = float(r.get("valor") or 0)

        if tipo == "ingreso":
            ingresos += valor
        elif tipo == "gasto":
            gastos += valor

    base = ingresos - gastos
    impuesto = base * 0.10 if base > 0 else 0.0

    # Nombre desde pestaña usuarios
    usuarios_ws = sheet.worksheet("usuarios")
    usuarios = usuarios_ws.get_all_records()

    nombre = "Contribuyente"
    for u in usuarios:
        if str(u.get("cedula", "")).strip() == cedula:
            nombre = u.get("nombre") or "Contribuyente"
            break

    return {
        "nombre": nombre,
        "ingresos": ingresos,
        "gastos": gastos,
        "base": base,
        "impuesto": impuesto
    }

# ===============================
# AUTO-SYNC SIN SCHEDULER (GATE)
# ===============================
SYNC_INTERVAL_SEC = 60

def maybe_sync():
    """
    No usamos scheduler (Render puede fallar).
    Hacemos "auto-sync" si ya pasó 1 minuto desde la última sync.
    Guardamos el timestamp en SQLite para que persista.
    """
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
    last_ts = float(row[0]) if row and row[0] else 0.0

    now = time.time()
    if now - last_ts < SYNC_INTERVAL_SEC:
        conn.close()
        return {"synced": False, "reason": "interval_not_reached"}

    try:
        nuevos = sync_transacciones()
        cur.execute("INSERT OR REPLACE INTO sync_state (k, v) VALUES ('last_sync_ts', ?)", (str(now),))
        conn.commit()
        conn.close()
        return {"synced": True, "nuevos": nuevos}
    except Exception as e:
        conn.close()
        print("Error en sync_transacciones:", e)
        return {"synced": False, "error": str(e)}

# ===============================
# RUTAS
# ===============================

@app.route("/")
def inicio():
    # Auto-sync suave cada vez que alguien entra (si ya pasó 1 min)
    maybe_sync()
    return render_template("index.html")

@app.route("/consultar", methods=["POST"])
def consultar():
    # Auto-sync suave antes de calcular (por si acaba de entrar una transacción)
    maybe_sync()

    cedula = request.form["cedula"].strip()

    if not usuario_existe_en_sheet(cedula):
        return "Usuario no encontrado"

    codigo = str(random.randint(100000, 999999))
    session["codigo"] = codigo
    session["cedula"] = cedula

    enviar_codigo(EMAIL, codigo)

    # En demo: mostramos código (aunque correo falle)
    return render_template("verificar.html", codigo_demo=codigo)

@app.route("/verificar", methods=["POST"])
def verificar():
    codigo_usuario = request.form["codigo"].strip()

    if codigo_usuario != session.get("codigo"):
        return "Código incorrecto"

    cedula = session.get("cedula")
    data = calcular_renta_desde_historial(cedula)

    return render_template("resultado.html", data=data)

# ✅ Sync manual por navegador (GET)
@app.route("/admin/sync")
def admin_sync():
    r = maybe_sync()
    # además, si quieres forzar SIEMPRE, puedes llamar directo:
    # nuevos = sync_transacciones()
    # return f"Forzado. Nuevos: {nuevos}"
    return f"Sync: {r}"

# (Opcional) Endpoint de salud
@app.route("/health")
def health():
    return {"ok": True}

# ===============================
# EJECUCIÓN
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
