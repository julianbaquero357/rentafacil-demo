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

def sync_transacciones():
    gc = conectar_google()

    sheet_bancos = gc.open_by_key(os.environ["SHEET_BANCOS_ID"]).worksheet("transacciones")
    sheet_usuarios = gc.open_by_key(os.environ["SHEET_USUARIOS_ID"])

    usuarios_ws = sheet_usuarios.worksheet("usuarios")
    historial_ws = sheet_usuarios.worksheet("historial")

    usuarios_data = usuarios_ws.get_all_records()
    usuarios = set(str(u["cedula"]).strip() for u in usuarios_data)

    transacciones = sheet_bancos.get_all_records()

    conn = sqlite3.connect("renta.db")
    cur = conn.cursor()

    # tabla para evitar duplicados
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transacciones_vistas (
            id_transaccion TEXT PRIMARY KEY
        )
    """)

    nuevos = 0

    for t in transacciones:
        tid = str(t["id_transaccion"]).strip()

        # evitar duplicados
        cur.execute("SELECT 1 FROM transacciones_vistas WHERE id_transaccion=?", (tid,))
        if cur.fetchone():
            continue

        descripcion = (t["descripcion"] or "").strip()
        cuenta_entrante = str(t["cuenta_entrante"]).strip()
        cuenta_saliente = str(t["cuenta_saliente"]).strip()
        valor = float(t["valor"])
        fecha = t["fecha"]

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

        # marcar como procesada
        cur.execute("INSERT INTO transacciones_vistas VALUES (?)", (tid,))

    conn.commit()
    conn.close()

    return nuevos
