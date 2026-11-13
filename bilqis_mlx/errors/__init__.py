"""Bilqis error control plane."""

from .bus import ErrorBus
from .catalog import CATALOG, FACTORY, SEMANTIC_COVERAGE, SEMANTIC_FRAME, SCHOOL, SOURCE
from .model import BilqisError, ErrorReport, ErrorSpec, RecoveryContract

__all__ = (
    "BilqisError",
    "CATALOG",
    "ErrorBus",
    "ErrorReport",
    "ErrorSpec",
    "FACTORY",
    "RecoveryContract",
    "SEMANTIC_COVERAGE",
    "SEMANTIC_FRAME",
    "SCHOOL",
    "SOURCE",
)
