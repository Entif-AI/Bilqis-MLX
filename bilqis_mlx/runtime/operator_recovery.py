"""Compatibility facade over the central Bilqis error control plane.

New code must use ``bilqis_mlx.errors.ErrorBus`` directly. This module keeps
older callers stable while the raw-string exception backlog is migrated.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..errors import ErrorBus


@dataclass(frozen=True)
class RecoveryAdvice:
    code: str
    disposition: str
    next_action: str


def error_code(error: BaseException | str) -> str:
    return ErrorBus.report(error).code


def recovery_advice(error: BaseException | str) -> RecoveryAdvice:
    report = ErrorBus.report(error)
    return RecoveryAdvice(report.code, report.disposition, report.next_action)
