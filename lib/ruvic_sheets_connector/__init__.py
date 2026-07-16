"""Conector Ruvic para Google Sheets."""

from .client import SheetsClient
from .config import ENV_PREFIX, SheetsConfig
from .exceptions import (
    SheetsAuthError,
    SheetsConnectorError,
    SheetsDataError,
    SheetsNetworkError,
)
from .logging_utils import setup_logging

__all__ = [
    "ENV_PREFIX",
    "SheetsAuthError",
    "SheetsClient",
    "SheetsConfig",
    "SheetsConnectorError",
    "SheetsDataError",
    "SheetsNetworkError",
    "setup_logging",
]

__version__ = "1.0.0"
