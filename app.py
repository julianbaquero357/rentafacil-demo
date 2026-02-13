from flask import Flask, render_template, request, session, redirect
import sqlite3
import os
import random
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "clave_demo_rentafacil"

# CONFIGURACIÓN DE CORREO
EMAIL = "rentafacildemo@gmail.com"
PASSWORD = "ujky bszn wpaj jckv"

def enviar_codigo(correo, codigo):
    msg = MIMEText(f"Su código de verificación es: {codigo}")
    msg["Subject"] = "Código de verificación - Renta Fácil"
    msg["From"] = EMAIL
    msg["To"] = correo

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL, PASSWORD)
        server.send_message(msg)

def calcular_renta(cedula):
    conn = sqlite3.connect("renta.db")
    cursor = conn.cursor()

    cursor.execute("SELECT nombre FROM usuarios WHERE cedula=?", (cedula,))
    user = cursor.fetchone()

    if not user:
        return None

    nombre = user[0]

    cursor.execute("SELECT SUM(monto) FROM transacciones WHERE cedula=? AND tipo='ingreso'", (cedula,))
    ingresos = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(monto) FROM transacciones WHERE cedula=? AND tipo='gasto'", (cedula,))
    gastos = cursor.fetchone()[0] or 0

    base = ingresos - gastos
    impuesto = base * 0.10 if base > 0 else 0

    conn.close()

    return {
        "nombre": nombre,
        "ingresos": ingresos,
        "gastos": gastos,
        "base": base,
        "impuesto": impuesto
    }

@app.route("/")
def inicio():
    return render_template("index.html")

@app.route("/consultar", methods=["POST"])
def consultar():
    cedula = request.form["cedula"]

    conn = sqlite3.connect("renta.db")
    cursor = conn.cursor()
    cursor.execute("SELECT correo FROM usuarios WHERE cedula=?", (cedula,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return "Usuario no encontrado"

    correo = user[0]

    codigo = str(random.randint(100000, 999999))
    session["codigo"] = codigo
    session["cedula"] = cedula

    enviar_codigo(correo, codigo)

    return render_template("verificar.html")

@app.route("/verificar", methods=["POST"])
def verificar():
    codigo_ingresado = request.form["codigo"]

    if codigo_ingresado == session.get("codigo"):
        cedula = session.get("cedula")
        resultado = calcular_renta(cedula)
        return render_template("resultado.html", data=resultado)
    else:
        return "Código incorrecto"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
