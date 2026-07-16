---
name: sheets
description: >
  Usa la librería ruvic_sheets_connector para leer y escribir hojas de
  cálculo de Google Sheets - leer un rango (read_range), escribir/sobrescribir
  valores en un rango (update_range) y agregar filas nuevas al final de una
  tabla (append_rows). Úsala cuando el usuario pida leer, consultar,
  actualizar o agregar datos a una hoja de cálculo de Google Sheets.
triggers:
- google sheets
- hoja de cálculo
- hoja de calculo
- spreadsheet
- excel de google
- planilla
---

# Conector Google Sheets (ruvic_sheets_connector)

Librería Python para leer y escribir hojas de cálculo de Google Sheets (cuenta personal o Google Workspace). Está **preinstalada en el runtime** cuando el conector está configurado (si no, instálala con `pip install git+https://github.com/Dgirto/Sheets.git#subdirectory=lib`). Usa la API oficial de Sheets con OAuth2 y un refresh token obtenido una única vez durante la configuración.

## Regla crítica de credenciales

El código generado **NUNCA hardcodea credenciales**. Siempre se leen de variables de entorno, disponibles cuando el conector `sheets` está configurado:

| Variable | Contenido |
|----------|-----------|
| `RUVIC_SHEETS_CLIENT_ID` | Client ID del cliente OAuth de Google Cloud |
| `RUVIC_SHEETS_CLIENT_SECRET` | Client Secret del mismo cliente OAuth |
| `RUVIC_SHEETS_REFRESH_TOKEN` | Refresh token obtenido al autorizar el acceso |
| `RUVIC_SHEETS_REQUEST_TIMEOUT` | (opcional) timeout en segundos, default 30 |

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en **Settings → Conectores**.

## Conexión (siempre igual)

```python
from ruvic_sheets_connector import SheetsClient

client = SheetsClient()  # lee RUVIC_SHEETS_* del entorno automáticamente
```

## Identificar la hoja de cálculo

El `spreadsheet_id` es el que aparece en la URL de la hoja:
`https://docs.google.com/spreadsheets/d/`**`ESTE_ID`**`/edit`. Si el usuario
pega la URL completa, extrae solo esa parte.

## Capacidad 1 — Leer un rango

```python
rows = client.read_range("1AbC...xyz", "Hoja1!A1:D20")
for row in rows:
    print(row)  # cada fila es una lista de valores de celda
```

`range` usa notación A1: `"Hoja1!A1:D20"` (rango específico), `"Hoja1"`
(toda la hoja), etc. Filas con celdas vacías al final pueden venir más
cortas que las demás.

## Capacidad 2 — Escribir/sobrescribir un rango

```python
result = client.update_range(
    "1AbC...xyz", "Hoja1!A2:B2", [["ACME", "Bogotá"]]
)
print(result["updated_cells"])
```

Sobrescribe exactamente las celdas del rango indicado. Usa esto cuando
sabes la posición exacta a actualizar (ej. una fila ya existente).

## Capacidad 3 — Agregar filas al final

```python
result = client.append_rows(
    "1AbC...xyz", "Hoja1", [["Nuevo cliente", "Medellín"]]
)
print(result["updated_range"])  # dónde quedaron las filas nuevas
```

Detecta automáticamente el final de la tabla de datos y agrega ahí, sin
sobrescribir filas existentes. Úsalo para "agregar una fila nueva" en vez
de `update_range` (evita tener que calcular la siguiente fila vacía).

## Manejo de errores

```python
from ruvic_sheets_connector import (
    SheetsAuthError, SheetsDataError, SheetsNetworkError,
)

try:
    client.append_rows("1AbC...xyz", "Hoja1", [["dato"]])
except SheetsAuthError:
    print("Credenciales inválidas o refresh token vencido — revisa la configuración del conector")
except SheetsNetworkError:
    print("Sheets API no respondió — puede ser un límite de cuota temporal")
except SheetsDataError as e:
    print(f"Error de datos: {e}")  # ej. la hoja no existe o no es accesible
```

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_SHEETS_*` (el constructor de `SheetsClient` ya lo hace).
2. Nunca imprimas `RUVIC_SHEETS_CLIENT_SECRET` ni `RUVIC_SHEETS_REFRESH_TOKEN` en logs ni en la salida.
3. El conector solo puede acceder a hojas que estén **compartidas con la cuenta autorizada** (o de su propiedad). Si `read_range`/`update_range`/`append_rows` fallan con "no existe o no es accesible", el usuario debe compartir la hoja con esa cuenta.
4. Usa `append_rows` para agregar datos nuevos; usa `update_range` solo cuando necesitas sobrescribir una posición específica.
5. El conector no crea ni elimina hojas de cálculo ni pestañas — solo lee y escribe valores dentro de hojas existentes.
