"""Typed error contracts for Bilqis runtime, factory, and operator surfaces.

An error identity is structured data. Human prose is a rendering of that data,
not the identity itself. This keeps code, recovery policy, tests, telemetry and
operator documentation bound to one stable contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

MIN_ERROR_PATH_SEGMENTS = 2


@dataclass(frozen=True)
class RecoveryContract:
    disposition: str
    next_action: str
    operator_steps: tuple[str, ...] = ()
    preserve_state: bool = True
    self_heal_owner: str | None = None

    def __post_init__(self) -> None:
        if (not self.disposition or not self.next_action or
                any(not isinstance(step, str) or not step
                    for step in self.operator_steps)):
            raise ValueError


@dataclass(frozen=True)
class ErrorSpec:
    path: tuple[str, ...]
    owner: str
    title: str
    message_key: str
    message_template: str
    recovery_key: str
    recovery: RecoveryContract
    legacy_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (len(self.path) < MIN_ERROR_PATH_SEGMENTS or
                any(not isinstance(part, str) or not part
                    for part in self.path) or
                not self.owner or not self.title or
                not self.message_key or not self.message_template or
                not self.recovery_key or
                not isinstance(self.recovery, RecoveryContract)):
            raise ValueError

    @property
    def code(self) -> str:
        return ".".join(self.path)

    def message(self, context: Mapping[str, object]) -> str:
        try:
            return self.message_template.format_map(dict(context))
        except KeyError:
            return self.title


class BilqisError(ValueError):
    """Structured domain error retaining ValueError compatibility during migration."""

    def __init__(self, spec: ErrorSpec, context: Mapping[str, object] | None = None):
        if not isinstance(spec, ErrorSpec):
            raise TypeError
        self.spec = spec
        self.context = MappingProxyType(dict(context or {}))
        super().__init__(spec.code)

    @property
    def code(self) -> str:
        return self.spec.code


@dataclass(frozen=True)
class ErrorReport:
    code: str
    title: str
    summary: str
    owner: str
    disposition: str
    next_action: str
    operator_steps: tuple[str, ...]
    preserve_state: bool
    self_heal_owner: str | None
    context: Mapping[str, object]
    legacy_untyped: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))

    def cli_lines(self) -> tuple[str, ...]:
        lines = [
            "OPERATOR BLOCKED: " + self.code,
            "WHAT HAPPENED: " + self.summary,
            "OWNER: " + self.owner,
            "RECOVERY: " + self.disposition + " | " + self.next_action,
        ]
        if self.self_heal_owner:
            lines.append("SELF-HEAL OWNER: " + self.self_heal_owner)
        if self.operator_steps:
            lines.append("OPERATOR STEPS:")
            lines.extend(
                f"  {index}. {step}"
                for index, step in enumerate(self.operator_steps, 1))
        if self.context:
            details = ", ".join(
                f"{key}={value}" for key, value in sorted(self.context.items()))
            lines.append("DETAILS: " + details)
        if self.legacy_untyped:
            lines.append(
                "MIGRATION DEBT: this failure still originates as an untyped "
                "legacy exception and is being normalized at the boundary.")
        return tuple(lines)
