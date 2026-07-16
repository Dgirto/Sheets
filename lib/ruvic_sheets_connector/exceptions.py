"""Excepciones propias del conector Google Sheets.

Separan los tres tipos de fallo que el usuario debe distinguir:
autenticación, red/servidor y datos. Nunca exponemos excepciones
crípticas del cliente HTTP subyacente.
"""


class SheetsConnectorError(Exception):
    """Error base del conector."""


class SheetsAuthError(SheetsConnectorError):
    """Credenciales inválidas, refresh token vencido o permisos insuficientes."""


class SheetsNetworkError(SheetsConnectorError):
    """No se pudo alcanzar la API de Sheets (red, timeout, error temporal del servidor)."""


class SheetsDataError(SheetsConnectorError):
    """La operación es válida pero el recurso no existe o los datos son inválidos."""
