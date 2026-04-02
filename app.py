from flask import Flask, render_template, request, session, redirect, send_file
from functools import wraps
import os
import json
import random
import sqlite3
import time
import io

import gspread
from google.oauth2.service_account import Credentials

from sheets_sync import sync_transacciones
from pdf_generator import generar_pdf_declaracion
from email_service import (
    enviar_codigo_verificacion,
    enviar_notificacion_pdf,
    correo_habilitado
)

app = Flask(__name__)
app.secret_key = "clave_demo_rentafacil"

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
# AUTO SYNC CONTROLADO
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
        return {"synced": False}

    try:
        nuevos = sync_transacciones()
        cur.execute(
            "INSERT OR REPLACE INTO sync_state (k, v) VALUES ('last_sync_ts', ?)",
            (str(now),)
        )
        conn.commit()
        conn.close()
        return {"synced": True, "nuevos": nuevos}
    except Exception as e:
        conn.close()
        print("Error sync:", e)
        return {"synced": False, "error": str(e)}

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
        usuario = request.form.get("usuario", "")
        password = request.form.get("password", "")

        if usuario == "admin" and password == "admin":
            session["admin_logged"] = True
            return redirect("/admin")

        return render_template("admin_login.html", error="Credenciales incorrectas")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect("/admin/login")

# =====================================================
# VALIDAR USUARIO
# =====================================================
def usuario_existe(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    ws = sheet.worksheet("usuarios")
    usuarios = ws.get_all_records()

    cedula = normalizar_cedula(cedula)
    return any(normalizar_cedula(u.get("cedula")) == cedula for u in usuarios)

# =====================================================
# OBTENER DATOS DE USUARIO
# =====================================================
def obtener_usuario_por_cedula(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    ws = sheet.worksheet("usuarios")
    usuarios = ws.get_all_records()

    cedula = normalizar_cedula(cedula)

    for u in usuarios:
        if normalizar_cedula(u.get("cedula")) == cedula:
            return {
                "cedula": cedula,
                "nombre": u.get("nombre", "Contribuyente"),
                "correo": u.get("correo") or "no-disponible@demo.co",
                "patrimonio": float(u.get("patrimonio") or 0),
                "deudas": float(u.get("deudas") or 0)
            }

    return None

# =====================================================
# CÁLCULO DE RENTA
# =====================================================
def calcular_renta(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    historial_ws = sheet.worksheet("historial")

    historial = historial_ws.get_all_records()
    usuario = obtener_usuario_por_cedula(cedula)

    cedula = normalizar_cedula(cedula)

    ingresos = 0.0
    gastos = 0.0

    for r in historial:
        if normalizar_cedula(r.get("cedula")) == cedula:
            tipo = (r.get("tipo") or "").strip().lower()
            valor = float(r.get("valor") or 0)

            if tipo == "ingreso":
                ingresos += valor
            elif tipo == "gasto":
                gastos += valor

    base = ingresos - gastos

    return {
        "nombre": usuario["nombre"] if usuario else "Contribuyente",
        "correo": usuario["correo"] if usuario else "no-disponible@demo.co",
        "patrimonio": usuario["patrimonio"] if usuario else 0,
        "deudas": usuario["deudas"] if usuario else 0,
        "ingresos": ingresos,
        "gastos": gastos,
        "base": base
    }

# =====================================================
# RUTAS PÚBLICAS
# =====================================================
@app.route("/")
def inicio():
    maybe_sync()
    return render_template("index.html")

@app.route("/acerca")
def acerca():
    return render_template("about.html")

@app.route("/consultar", methods=["POST"])
def consultar():
    maybe_sync()

    cedula = request.form.get("cedula", "")
    cedula = normalizar_cedula(cedula)

    if not usuario_existe(cedula):
        return "Usuario no encontrado"

    usuario = obtener_usuario_por_cedula(cedula)
    correo = usuario["correo"] if usuario else "no-disponible@demo.co"

    codigo = str(random.randint(100000, 999999))
    session["codigo"] = codigo
    session["cedula"] = cedula

    # Si correo real está habilitado, intenta enviar
    if correo_habilitado():
        try:
            enviar_codigo_verificacion(correo, codigo)
        except Exception as e:
            print("Error enviando verificación con Resend:", e)

    # En demo, siempre mostramos el código también
    return render_template("verificar.html", codigo_demo=codigo)

@app.route("/verificar", methods=["POST"])
def verificar():
    codigo_usuario = request.form.get("codigo", "").strip()

    if codigo_usuario != session.get("codigo"):
        return "Código incorrecto"

    cedula = session.get("cedula")
    if not cedula:
        return redirect("/")

    resultado = calcular_renta(cedula)

    return render_template("resultado.html", data=resultado)

# =====================================================
# PANEL ADMIN
# =====================================================
@app.route("/admin")
@login_required
def admin_panel():
    maybe_sync()

    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios = sheet.worksheet("usuarios").get_all_records()
    historial = sheet.worksheet("historial").get_all_records()

    total_ingresos = 0.0
    total_gastos = 0.0

    for r in historial:
        tipo = (r.get("tipo") or "").strip().lower()
        valor = float(r.get("valor") or 0)

        if tipo == "ingreso":
            total_ingresos += valor
        elif tipo == "gasto":
            total_gastos += valor

    total_base = total_ingresos - total_gastos

    return render_template(
        "admin.html",
        total_usuarios=len(usuarios),
        total_ingresos=total_ingresos,
        total_gastos=total_gastos,
        total_base=total_base
    )

@app.route("/admin/usuario", methods=["POST"])
@login_required
def admin_usuario():
    maybe_sync()

    cedula = request.form.get("cedula", "")
    cedula = normalizar_cedula(cedula)

    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    historial_ws = sheet.worksheet("historial")
    historial = historial_ws.get_all_records()

    usuario = obtener_usuario_por_cedula(cedula)

    if not usuario:
        return "Usuario no encontrado"

    transacciones = []
    ingresos = 0.0
    gastos = 0.0

    for r in historial:
        if normalizar_cedula(r.get("cedula")) == cedula:
            tipo = (r.get("tipo") or "").strip().lower()
            valor = float(r.get("valor") or 0)

            transacciones.append({
                "id_transaccion": r.get("id_transaccion") or r.get("id") or "",
                "tipo": tipo,
                "descripcion": r.get("descripcion") or "",
                "valor": valor
            })

            if tipo == "ingreso":
                ingresos += valor
            elif tipo == "gasto":
                gastos += valor

    base = ingresos - gastos

    return render_template(
        "admin_usuario.html",
        nombre=usuario["nombre"],
        cedula=usuario["cedula"],
        correo=usuario["correo"],
        ingresos=ingresos,
        gastos=gastos,
        base=base,
        patrimonio=usuario["patrimonio"],
        deudas=usuario["deudas"],
        transacciones=transacciones
    )

@app.route("/admin/pdf/<cedula>")
@login_required
def admin_pdf(cedula):
    maybe_sync()

    cedula = normalizar_cedula(cedula)
    resultado = calcular_renta(cedula)

    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    historial = sheet.worksheet("historial").get_all_records()

    transacciones = []
    for r in historial:
        if normalizar_cedula(r.get("cedula")) == cedula:
            transacciones.append({
                "id_transaccion": r.get("id_transaccion") or r.get("id") or "",
                "tipo": (r.get("tipo") or "").strip().lower(),
                "descripcion": r.get("descripcion") or "",
                "valor": float(r.get("valor") or 0)
            })

    data_pdf = {
        "cedula": cedula,
        "nombre": resultado["nombre"],
        "correo": resultado["correo"],
        "ingresos": resultado["ingresos"],
        "gastos": resultado["gastos"],
        "base": resultado["base"],
        "patrimonio": resultado["patrimonio"],
        "deudas": resultado["deudas"],
        "transacciones": transacciones
    }

    pdf_bytes = generar_pdf_declaracion(data_pdf)
    filename = f"Declaracion_RentaFacil_210_DEMO_{cedula}_AG2025.pdf"

    # Si correo real está habilitado, manda notificación
    if correo_habilitado():
        try:
            enviar_notificacion_pdf(resultado["correo"], resultado["nombre"], cedula)
        except Exception as e:
            print("Error enviando notificación PDF:", e)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@app.route("/admin/sync")
@login_required
def admin_sync():
    res = maybe_sync()
    return f"Sync: {res}"

# =====================================================
# HEALTH
# =====================================================
@app.route("/health")
def health():
    return {"ok": True}

# =====================================================
# EJECUCIÓN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
