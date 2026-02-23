import os
import json
import sqlite3
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def conectar_google():
    sa_json = json.loads(os.environ["GOOGLE_SA_JSON"])
    creds = Credentials.from_service_account_info(sa_json, scopes=SCOPES)
    return gspread.authorize(creds)

def normalizar_cedula(valor):
    """
    Convierte cualquier valor (1001, 1001.0, '1001', ' 1001 ') 
    en string limpio: '1001'
    """
    if valor is None:
        return ""
    try:
        return str(int(float(valor))).strip()
    except:
        return str(valor).strip()

def sync_transacciones():
    gc = conectar_google()

    sheet_bancos = gc.open_by_key(os.environ["SHEET_BANCOS_ID"]).worksheet("transacciones")
    sheet_usuarios = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])

    usuarios_ws = sheet_usuarios.worksheet("usuarios")
    historial_ws = sheet_usuarios.worksheet("historial")

    usuarios_data = usuarios_ws.get_all_records()

    usuarios = set(normalizar_cedula(u["cedula"]) for u in usuarios_data)

    transacciones = sheet_bancos.get_all_records()

    conn = sqlite3.connect("renta.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transacciones_vistas (
            id_transaccion TEXT PRIMARY KEY
        )
    """)

    nuevos = 0

    for t in transacciones:

        tid = str(t["id_transaccion"]).strip()

        cur.execute("SELECT 1 FROM transacciones_vistas WHERE id_transaccion=?", (tid,))
        if cur.fetchone():
            continue

        descripcion = (t["descripcion"] or "").strip()
        cuenta_entrante = normalizar_cedula(t["cuenta_entrante"])
        cuenta_saliente = normalizar_cedula(t["cuenta_saliente"])
        valor = float(t["valor"])
        fecha = str(t["fecha"])

        # INGRESO
        if cuenta_entrante in usuarios:
            desc_final = descripcion if descripcion else "ingreso diario"

            historial_ws.append_row([
                cuenta_entrante,
                tid,
                "ingreso",
                desc_final,
                valor,
                fecha
            ])
            nuevos += 1

        # GASTO
        if cuenta_saliente in usuarios:
            desc_final = descripcion if descripcion else "gasto diario"

            historial_ws.append_row([
                cuenta_saliente,
                tid,
                "gasto",
                desc_final,
                valor,
                fecha
            ])
            nuevos += 1

        cur.execute("INSERT INTO transacciones_vistas VALUES (?)", (tid,))

    conn.commit()
    conn.close()

    return nuevos
