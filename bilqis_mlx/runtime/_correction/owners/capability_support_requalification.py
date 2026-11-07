"""Durable requalification install and cold rehydration for support owners."""
from __future__ import annotations

from dataclasses import replace

from .atlas_requalification_contracts import (
    RequalificationLedger, RequalificationStatus, RequalificationUpdate,
)
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_runtime import apply_correction
from .atlas_source_authority import SourceAuthorityRegistry
from .capability_support_journal import event_from_record, transition_from_record


def install_ledger(owner, ledger: RequalificationLedger) -> None:
    if not isinstance(ledger, RequalificationLedger) or len(ledger.capabilities) != 1:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_REQUALIFICATION_DRIFT")
    current = owner.support
    updated = ledger.capability(owner.capability_id)
    if (replace(current, status=RequalificationStatus.QUALIFIED)
            != replace(updated, status=RequalificationStatus.QUALIFIED)):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_REQUALIFICATION_DRIFT")
    owner._ledger = ledger


def install_requalification(owner, update: RequalificationUpdate) -> None:
    if (not isinstance(update, RequalificationUpdate)
            or owner.capability_id not in update.affected_capability_ids):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_REQUALIFICATION_DRIFT")
    ledger = update.ledger
    support = ledger.capability(owner.capability_id)
    install_ledger(owner, RequalificationLedger(
        capabilities=(support,),
        historical=tuple(item for item in ledger.historical
                         if item.capability_id == owner.capability_id),
        pending_source_tasks=tuple(item for item in ledger.pending_source_tasks
                                   if item.capability_id == owner.capability_id),
        pending_c10_intents=tuple(item for item in ledger.pending_c10_intents
                                  if owner.capability_id in item.capability_ids),
    ))


def rehydrate_support_hold(owner, hold, node, authority_registry):
    if hold is None:
        return owner
    if not isinstance(authority_registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_CORRECTION_AUTHORITY_REQUIRED")
    event = event_from_record(hold.get("event"))
    authority_registry.verify_correction(event)
    transition = transition_from_record(hold.get("transition"))
    encoded_ledger = hold.get("requalification_ledger")
    if encoded_ledger is not None:
        from bilqis_mlx.runtime.accepted_requalification_codec import ledger_from_record
        install_ledger(owner, ledger_from_record(encoded_ledger))
    if transition is not None:
        authority_registry.verify_transition(transition)
        if (transition.artifact_id != node.artifact_id
                or transition.correction_event_id != event.event_id
                or transition.correction_receipt_sha256 != event.source_receipt_sha256
                or transition.previous_content_digest != node.content_digest
                or transition.previous_eligible != node.eligible
                or transition.immediate_dependencies != node.immediate_dependencies):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
    if hold["state"] == "CLEARED":
        if transition is None or transition.changed:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
        return owner
    if hold["state"] == "REQUALIFICATION_REQUIRED":
        if transition is None or not transition.changed:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
        if encoded_ledger is None:
            install_ledger(owner, RequalificationLedger((replace(
                owner.support,
                status=RequalificationStatus.REQUALIFICATION_REQUIRED,
            ),)))
        elif owner.support.status is not RequalificationStatus.REQUALIFICATION_REQUIRED:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
        return owner
    if transition is not None:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
    owner._queue = apply_correction(event, owner._index, authority_registry)
    return owner


__all__ = ("install_ledger", "install_requalification", "rehydrate_support_hold")
