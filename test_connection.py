"""Prueba de conexión estándar del conector sheets.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_SHEETS_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Valida las credenciales OAuth de Sheets (refresca el access token)
    usando las env vars RUVIC_SHEETS_*."""
    try:
        from ruvic_sheets_connector import (
            SheetsAuthError,
            SheetsClient,
            SheetsDataError,
            SheetsNetworkError,
        )
    except ImportError:
        return (
            False,
            "La librería ruvic-sheets-connector no está instalada. "
            "Instala con: pip install git+https://github.com/Dgirto/"
            "Sheets.git#subdirectory=lib",
        )

    try:
        client = SheetsClient()  # valida que existan las env vars
    except ValueError as exc:
        return False, str(exc)

    try:
        client.ping()
    except SheetsAuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except SheetsNetworkError as exc:
        return False, f"Error de red: {exc}"
    except SheetsDataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return (True, "Conexión exitosa: credenciales OAuth de Sheets válidas")


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)
