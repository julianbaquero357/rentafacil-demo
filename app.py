from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)

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
    resultado = calcular_renta(cedula)

    if not resultado:
        return "Usuario no encontrado"

    return render_template("resultado.html", data=resultado)

if __name__ == "__main__":
    app.run(debug=True)
