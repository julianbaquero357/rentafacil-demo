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

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def conectar_google():
    sa_json = json.loads(os.environ["GOOGLE_SA_JSON"])
    creds = Credentials.from_service_account_info(sa_json, scopes=SCOPES)
    return gspread.authorize(creds)


def normalizar_cedula(valor):
    try:
        return str(int(float(valor))).strip()
    except:
        return str(valor).strip()


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
        if request.form["usuario"] == "admin" and request.form["password"] == "admin":
            session["admin_logged"] = True
            return redirect("/admin")

        return render_template("admin_login.html", error="Credenciales incorrectas")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect("/admin/login")


# =====================================================
# USUARIO
# =====================================================
def usuario_existe(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios = sheet.worksheet("usuarios").get_all_records()

    return any(normalizar_cedula(u["cedula"]) == cedula for u in usuarios)


def obtener_usuario(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    usuarios = sheet.worksheet("usuarios").get_all_records()

    for u in usuarios:
        if normalizar_cedula(u["cedula"]) == cedula:
            return u
    return None


# =====================================================
# CALCULO
# =====================================================
def calcular_renta(cedula):
    gc = conectar_google()
    sheet = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])
    historial = sheet.worksheet("historial").get_all_records()

    ingresos = 0
    gastos = 0

    for r in historial:
        if normalizar_cedula(r["cedula"]) == cedula:
            if r["tipo"] == "ingreso":
                ingresos += float(r["valor"])
            else:
                gastos += float(r["valor"])

    base = ingresos - gastos

    usuario = obtener_usuario(cedula)

    return {
        "nombre": usuario["nombre"],
        "correo": usuario.get("correo", ""),
        "ingresos": ingresos,
        "gastos": gastos,
        "base": base
    }


# =====================================================
# RUTAS
# =====================================================
@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/acerca")
def acerca():
    return render_template("about.html")


@app.route("/consultar", methods=["POST"])
def consultar():
    cedula = normalizar_cedula(request.form["cedula"])

    if not usuario_existe(cedula):
        return "Usuario no encontrado"

    codigo = str(random.randint(100000, 999999))

    session["codigo"] = codigo
    session["cedula"] = cedula

    # 🔥 ENVÍO OBLIGATORIO
    try:
        enviar_codigo_verificacion(codigo)
    except Exception as e:
        return f"Error enviando correo: {e}"

    return render_template("verificar.html")


@app.route("/verificar", methods=["POST"])
def verificar():
    if request.form["codigo"] != session.get("codigo"):
        return render_template("verificar.html", error="Código incorrecto")

    resultado = calcular_renta(session["cedula"])
    return render_template("resultado.html", data=resultado)


# =====================================================
# PDF
# =====================================================
@app.route("/admin/pdf/<cedula>")
@login_required
def admin_pdf(cedula):
    resultado = calcular_renta(cedula)

    pdf_bytes = generar_pdf_declaracion(resultado)

    try:
        enviar_notificacion_pdf(resultado["nombre"], cedula)
    except:
        pass

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"declaracion_{cedula}.pdf"
    )


# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
