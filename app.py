from flask import Flask, render_template, request, session, redirect
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "clave_demo_rentafacil"

# ===============================
# CONFIGURACIÓN DEL CORREO DEMO
# ===============================
EMAIL = "rentafacildemo@gmail.com"
PASSWORD = "ujky bszn wpaj jckv"   # contraseña de aplicación

# ===============================
# FUNCIÓN PARA ENVIAR CÓDIGO
# ===============================
def enviar_codigo(correo, codigo):
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
        print("Código de verificación:", codigo)

# ===============================
# CÁLCULO DE RENTA
# ===============================
def calcular_renta(cedula):
    conn = sqlite3.connect("renta.db")
    cursor = conn.cursor()

    cursor.execute("SELECT nombre FROM usuarios WHERE cedula=?", (cedula,))
    user = cursor.fetchone()

    if not user:
        return None

    nombre = user[0]

    cursor.execute(
        "SELECT SUM(monto) FROM transacciones WHERE cedula=? AND tipo='ingreso'",
        (cedula,))
    ingresos = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT SUM(monto) FROM transacciones WHERE cedula=? AND tipo='gasto'",
        (cedula,))
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

# ===============================
# RUTAS
# ===============================

@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/consultar", methods=["POST"])
def consultar():
    cedula = request.form["cedula"]

    conn = sqlite3.connect("renta.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM usuarios WHERE cedula=?", (cedula,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return "Usuario no encontrado"

    # Generar código
    codigo = str(random.randint(100000, 999999))
    session["codigo"] = codigo
    session["cedula"] = cedula

    correo = EMAIL  # correo demo único
    enviar_codigo(correo, codigo)

    # Mostrar código en pantalla si el correo falla
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
# EJECUCIÓN
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
