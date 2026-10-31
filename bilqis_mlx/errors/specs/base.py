"""Typed base error contracts."""
from __future__ import annotations

from ..model import ErrorSpec, RecoveryContract

def _spec(
    path: tuple[str, ...], *,
    owner: str,
    title: str,
    message_template: str,
    disposition: str,
    next_action: str,
    operator_steps: tuple[str, ...] = (),
    self_heal_owner: str | None = None,
    legacy_codes: tuple[str, ...] = (),
) -> ErrorSpec:
    key = ".".join(path).lower()
    return ErrorSpec(
        path=path,
        owner=owner,
        title=title,
        message_key="errors." + key + ".message",
        message_template=message_template,
        recovery_key="errors." + key + ".recovery",
        recovery=RecoveryContract(
            disposition=disposition,
            next_action=next_action,
            operator_steps=operator_steps,
            preserve_state=True,
            self_heal_owner=self_heal_owner,
        ),
        legacy_codes=legacy_codes,
    )
