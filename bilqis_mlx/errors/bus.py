"""Single ingress/egress point for typed and legacy Bilqis failures."""
from __future__ import annotations

from typing import NoReturn

from .catalog import BY_CODE, BY_LEGACY_CODE
from .legacy import legacy_report
from .model import BilqisError, ErrorReport, ErrorSpec


class ErrorBus:
    @staticmethod
    def Raise(spec: ErrorSpec, **context: object) -> NoReturn:
        """Public compositional raise form used by domain code."""
        raise BilqisError(spec, context)

    @staticmethod
    def raise_(spec: ErrorSpec, **context: object) -> NoReturn:
        """Compatibility spelling for callers written before Raise."""
        ErrorBus.Raise(spec, **context)

    @staticmethod
    def report(error: BaseException | str) -> ErrorReport:
        if isinstance(error, BilqisError):
            spec = error.spec
            recovery = spec.recovery
            return ErrorReport(
                code=spec.code,
                title=spec.title,
                summary=spec.message(error.context),
                owner=spec.owner,
                disposition=recovery.disposition,
                next_action=recovery.next_action,
                operator_steps=recovery.operator_steps,
                preserve_state=recovery.preserve_state,
                self_heal_owner=recovery.self_heal_owner,
                context=error.context,
                legacy_untyped=False,
            )
        return legacy_report(error)

    @staticmethod
    def explain(code: str) -> tuple[ErrorReport, ...]:
        """Resolve a typed code or show every invariant hidden by a legacy code."""
        if code in BY_CODE:
            return (ErrorBus.report(BilqisError(BY_CODE[code])),)
        legacy_matches = BY_LEGACY_CODE.get(code, ())
        if legacy_matches:
            return tuple(
                ErrorBus.report(BilqisError(spec))
                for spec in legacy_matches
            )
        return (legacy_report(code),)
