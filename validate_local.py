"""Validacion local del conector sheets: ejercita las 3 capacidades.

Uso:
    export VALIDATE_SPREADSHEET_ID=<id_de_una_hoja_de_prueba>
    python validate_local.py

VALIDATE_SPREADSHEET_ID es solo para esta prueba local (no es una env var
del conector): el ID de una hoja de calculo real, accesible por la cuenta
que autorizo el refresh token, con una pestana llamada "Hoja1".
"""

import os

from ruvic_sheets_connector import SheetsClient, setup_logging

setup_logging("INFO")

spreadsheet_id = os.environ.get("VALIDATE_SPREADSHEET_ID")
if not spreadsheet_id:
    raise SystemExit(
        "Exporta VALIDATE_SPREADSHEET_ID con el ID de una hoja de prueba "
        "(de la URL: docs.google.com/spreadsheets/d/<ID>/edit)."
    )

client = SheetsClient()

print("== 1. Leer rango A1:D20 de Hoja1 ==")
rows = client.read_range(spreadsheet_id, "Hoja1!A1:D20")
for row in rows:
    print(f"  {row}")

print("== 2. Escribir en A1:B1 ==")
result = client.update_range(
    spreadsheet_id, "Hoja1!A1:B1", [["validate_local", "prueba de escritura"]]
)
print(f"  {result}")

print("== 3. Agregar fila al final ==")
result = client.append_rows(
    spreadsheet_id, "Hoja1", [["fila agregada", "por validate_local.py"]]
)
print(f"  {result}")
