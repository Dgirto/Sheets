"""Cliente de Google Sheets (cuenta personal o Google Workspace) vía OAuth2
con refresh token de usuario.

Capacidades:
- read_range():   leer los valores de un rango de una hoja.
- update_range():  escribir/sobrescribir valores en un rango existente.
- append_rows():  agregar filas nuevas al final de una hoja.

Las credenciales SIEMPRE provienen de variables de entorno RUVIC_SHEETS_*
(ver config.SheetsConfig.from_env). Prohibido hardcodearlas.
"""

from __future__ import annotations

import socket
from typing import Any

from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import SheetsConfig
from .exceptions import (
    SheetsAuthError,
    SheetsConnectorError,
    SheetsDataError,
    SheetsNetworkError,
)
from .logging_utils import get_logger

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _service_disabled_info(exc: HttpError) -> tuple[str, str] | None:
    """Detecta el caso 403 SERVICE_DISABLED (la API no está habilitada en
    el proyecto de Google Cloud) y retorna (nombre de la API, URL de
    activación), o None si el error es de otro tipo."""
    try:
        details = exc.error_details or []
    except Exception:
        details = []
    for detail in details:
        if isinstance(detail, dict) and detail.get("reason") == "SERVICE_DISABLED":
            meta = detail.get("metadata", {})
            return (
                meta.get("serviceTitle", "API de Google"),
                meta.get(
                    "activationUrl",
                    "Google Cloud Console -> APIs y servicios -> Biblioteca",
                ),
            )
    return None


def _wrap_http_error(exc: HttpError) -> SheetsConnectorError:
    """Traduce un error HTTP de la API de Sheets a una excepción propia,
    sin dejar escapar nunca el tipo crudo del cliente HTTP."""
    status = exc.resp.status if getattr(exc, "resp", None) is not None else None
    if status == 403:
        disabled = _service_disabled_info(exc)
        if disabled is not None:
            service_title, activation_url = disabled
            return SheetsAuthError(
                f"La {service_title} no está habilitada en el proyecto de "
                f"Google Cloud del Client ID configurado. Habilítala en "
                f"{activation_url} y espera 1-2 minutos antes de reintentar."
            )
    if status in (401, 403):
        return SheetsAuthError(
            "Credenciales inválidas o sin permiso suficiente sobre esta hoja. "
            "Verifica que el refresh token no esté revocado o vencido, que se "
            "haya autorizado con el scope de Sheets, y que la cuenta autenticada "
            "tenga acceso a la hoja de cálculo (compartida con ella si es de "
            "otro usuario)."
        )
    if status == 404:
        return SheetsDataError(
            "La hoja de cálculo o el rango solicitado no existe, o la cuenta "
            "autenticada no tiene acceso a ella."
        )
    if status == 429 or (status is not None and status >= 500):
        return SheetsNetworkError(
            f"Sheets API no respondió correctamente (HTTP {status}). "
            "Puede ser un límite de cuota temporal; reintenta en unos segundos."
        )
    return SheetsDataError(f"Error de Sheets API (HTTP {status}): {exc}")


_VALID_VALUE_INPUT_OPTIONS = {"USER_ENTERED", "RAW"}


def _validate_spreadsheet_id(spreadsheet_id: Any) -> str:
    if not isinstance(spreadsheet_id, str):
        raise SheetsDataError(
            f"spreadsheet_id debe ser un string, no {type(spreadsheet_id).__name__}."
        )
    spreadsheet_id = spreadsheet_id.strip()
    if not spreadsheet_id:
        raise SheetsDataError("spreadsheet_id no puede estar vacío.")
    return spreadsheet_id


def _validate_range(range_name: Any) -> str:
    if not isinstance(range_name, str):
        raise SheetsDataError(f"range debe ser un string, no {type(range_name).__name__}.")
    range_name = range_name.strip()
    if not range_name:
        raise SheetsDataError(
            "range no puede estar vacío (ej. 'Hoja1!A1:D20' o 'Hoja1')."
        )
    return range_name


def _validate_value_input_option(value_input_option: Any) -> str:
    if value_input_option not in _VALID_VALUE_INPUT_OPTIONS:
        raise SheetsDataError(
            f"value_input_option={value_input_option!r} inválido. "
            f"Valores permitidos: {sorted(_VALID_VALUE_INPUT_OPTIONS)}."
        )
    return value_input_option


class SheetsClient:
    """Cliente de Google Sheets para leer y escribir hojas de cálculo.

    Args:
        config: configuración de conexión. Si se omite, se lee de las
            variables de entorno RUVIC_SHEETS_* (comportamiento estándar
            en el runtime de la plataforma).

    Ejemplo:
        >>> client = SheetsClient()          # lee RUVIC_SHEETS_* del entorno
        >>> client.read_range("1AbC...xyz", "Hoja1!A1:C10")
        [['nombre', 'ciudad'], ['ACME', 'Bogotá']]
    """

    def __init__(self, config: SheetsConfig | None = None) -> None:
        self.config = config or SheetsConfig.from_env()
        self._logger = get_logger()
        self._service: Any = None
        self._credentials: Credentials | None = None

    # ------------------------------------------------------------------ #
    # Conexión
    # ------------------------------------------------------------------ #

    def _get_credentials(self) -> Credentials:
        if self._credentials is None:
            self._credentials = Credentials(
                token=None,
                refresh_token=self.config.refresh_token,
                token_uri=_TOKEN_URI,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                scopes=_SCOPES,
            )
        return self._credentials

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        credentials = self._get_credentials()
        try:
            self._service = build(
                "sheets",
                "v4",
                credentials=credentials,
                cache_discovery=False,
                static_discovery=False,
            )
        except (GoogleAuthError, OSError) as exc:
            raise SheetsNetworkError(
                f"No se pudo inicializar el cliente de Sheets: {exc}"
            ) from exc
        return self._service

    def ping(self) -> bool:
        """Verifica que las credenciales OAuth sean válidas refrescando el
        token de acceso (no requiere una hoja de cálculo específica).

        Returns:
            True si las credenciales funcionan.

        Raises:
            SheetsAuthError / SheetsNetworkError según el fallo.
        """
        credentials = self._get_credentials()
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            raise SheetsAuthError(
                "No se pudo autenticar: el refresh token puede estar revocado, "
                "vencido, o el client_id/client_secret no corresponden al mismo "
                "cliente OAuth con el que se generó. Vuelve a autorizar el "
                "conector para obtener un refresh token nuevo."
            ) from exc
        except (socket.error, TimeoutError, OSError) as exc:
            raise SheetsNetworkError(f"No se pudo conectar con Google OAuth: {exc}") from exc
        self._logger.info("Ping exitoso: credenciales OAuth válidas.")
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1: leer un rango
    # ------------------------------------------------------------------ #

    def read_range(self, spreadsheet_id: str, range_name: str) -> list[list[Any]]:
        """Lee los valores de un rango de una hoja de cálculo.

        Args:
            spreadsheet_id: ID de la hoja (de la URL:
                docs.google.com/spreadsheets/d/{spreadsheet_id}/edit).
            range_name: rango en notación A1 (ej. "Hoja1!A1:D20", o solo
                "Hoja1" para toda la hoja).

        Returns:
            Lista de filas; cada fila es una lista de valores de celda
            (strings/números tal como los interpreta Sheets). Las filas
            pueden tener distinta longitud si hay celdas vacías al final.

        Ejemplo:
            >>> client.read_range("1AbC...xyz", "Hoja1!A1:C3")
            [['nombre', 'ciudad'], ['ACME', 'Bogotá'], ['Globex', 'Medellín']]
        """
        spreadsheet_id = _validate_spreadsheet_id(spreadsheet_id)
        range_name = _validate_range(range_name)
        service = self._get_service()
        try:
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_name)
                .execute(num_retries=1)
            )
        except (RefreshError, GoogleAuthError) as exc:
            raise SheetsAuthError(
                f"No se pudo autenticar: el token OAuth/credenciales pueden "
                f"estar revocados, vencidos o ser inválidos. Vuelve a "
                f"autorizar el conector. Detalle: {exc}"
            ) from exc
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc
        values = result.get("values", [])
        self._logger.info(
            "Leídas %d filas de %s!%s", len(values), spreadsheet_id, range_name
        )
        return values

    # ------------------------------------------------------------------ #
    # Capacidad 2: escribir/actualizar un rango
    # ------------------------------------------------------------------ #

    def update_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """Escribe (sobrescribe) valores en un rango existente.

        Args:
            spreadsheet_id: ID de la hoja.
            range_name: rango en notación A1 donde empezar a escribir
                (ej. "Hoja1!A2").
            values: lista de filas a escribir; cada fila es una lista de
                valores de celda.
            value_input_option: "USER_ENTERED" (interpreta fórmulas y
                formatos como si el usuario tipeara, default) o "RAW"
                (guarda el valor literal sin interpretar).

        Returns:
            Dict con: updated_range, updated_rows, updated_cells.

        Ejemplo:
            >>> client.update_range("1AbC...xyz", "Hoja1!A2", [["ACME", "Bogotá"]])
            {'updated_range': 'Hoja1!A2:B2', 'updated_rows': 1, 'updated_cells': 2}
        """
        spreadsheet_id = _validate_spreadsheet_id(spreadsheet_id)
        range_name = _validate_range(range_name)
        value_input_option = _validate_value_input_option(value_input_option)
        service = self._get_service()
        try:
            result = (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    body={"values": values},
                )
                .execute(num_retries=1)
            )
        except (RefreshError, GoogleAuthError) as exc:
            raise SheetsAuthError(
                f"No se pudo autenticar: el token OAuth/credenciales pueden "
                f"estar revocados, vencidos o ser inválidos. Vuelve a "
                f"autorizar el conector. Detalle: {exc}"
            ) from exc
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc
        self._logger.info(
            "Actualizadas %d celdas en %s!%s",
            result.get("updatedCells", 0),
            spreadsheet_id,
            range_name,
        )
        return {
            "updated_range": result.get("updatedRange"),
            "updated_rows": result.get("updatedRows"),
            "updated_cells": result.get("updatedCells"),
        }

    # ------------------------------------------------------------------ #
    # Capacidad 3: agregar filas al final
    # ------------------------------------------------------------------ #

    def append_rows(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """Agrega filas nuevas al final de la tabla de datos existente.

        Google Sheets detecta automáticamente el final de la tabla dentro
        del rango indicado y agrega las filas justo después, sin
        sobrescribir datos existentes.

        Args:
            spreadsheet_id: ID de la hoja.
            range_name: rango/hoja donde buscar el final de la tabla
                (ej. "Hoja1" o "Hoja1!A:D").
            values: lista de filas a agregar.
            value_input_option: "USER_ENTERED" (default) o "RAW".

        Returns:
            Dict con: updated_range (rango real donde quedaron las filas
            nuevas), updated_rows, updated_cells.

        Ejemplo:
            >>> client.append_rows("1AbC...xyz", "Hoja1", [["Nuevo", "Cliente"]])
            {'updated_range': 'Hoja1!A15:B15', 'updated_rows': 1, 'updated_cells': 2}
        """
        spreadsheet_id = _validate_spreadsheet_id(spreadsheet_id)
        range_name = _validate_range(range_name)
        value_input_option = _validate_value_input_option(value_input_option)
        service = self._get_service()
        try:
            result = (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    insertDataOption="INSERT_ROWS",
                    body={"values": values},
                )
                .execute(num_retries=1)
            )
        except (RefreshError, GoogleAuthError) as exc:
            raise SheetsAuthError(
                f"No se pudo autenticar: el token OAuth/credenciales pueden "
                f"estar revocados, vencidos o ser inválidos. Vuelve a "
                f"autorizar el conector. Detalle: {exc}"
            ) from exc
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc
        updates = result.get("updates", {})
        self._logger.info(
            "Agregadas %d filas a %s!%s",
            updates.get("updatedRows", 0),
            spreadsheet_id,
            range_name,
        )
        return {
            "updated_range": updates.get("updatedRange"),
            "updated_rows": updates.get("updatedRows"),
            "updated_cells": updates.get("updatedCells"),
        }
