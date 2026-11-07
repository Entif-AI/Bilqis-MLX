"""Accepted-run stale-replay detection over the actual registered owner graph."""
from __future__ import annotations

from dataclasses import replace

from .accepted_correction_ledger import accepted_corrections, append_record, read_records
from .accepted_stale_replay_ledger import (
    DERIVED_CLAIM_EVENT, PROCESS_FAULT_EVENT, REMEDIATION_EVENT,
    derived_claim_from_record, process_fault_from_record, process_fault_record,
    remediation_from_record,
)
from .atlas_requalification import RequalificationLedger
from .atlas_requalification_contracts import RequalificationStatus
from .atlas_revalidation_common import _invalid
from .atlas_stale_replay import escalate_stale_replay
from bilqis_mlx.semantics.cognitive_dependencies import DependencyIndex, DependencyKind


def _registered_index(targets) -> DependencyIndex | None:
    nodes = {}
    for target in targets:
        owner = target.owner
        index = getattr(owner, "index", None)
        if not isinstance(index, DependencyIndex):
            continue
        for node in index.nodes:
            prior = nodes.get(node.artifact_id)
            if prior is not None and prior != node:
                _invalid("BAMF_C09_REGISTERED_OWNER_INDEX_CONFLICT")
            nodes[node.artifact_id] = node
    if not nodes:
        return None
    identifiers = set(nodes)
    if any(
        dependency.kind is DependencyKind.ARTIFACT
        and dependency.key not in identifiers
        for node in nodes.values()
        for dependency in node.immediate_dependencies
    ):
        return None
    return DependencyIndex.build(tuple(nodes.values()))


def _registered_requalification(targets) -> RequalificationLedger | None:
    supports = {}
    for target in targets:
        ledger = getattr(target.owner, "ledger", None)
        if not isinstance(ledger, RequalificationLedger):
            continue
        for support in ledger.capabilities:
            prior = supports.get(support.capability_id)
            if prior is not None and prior != support:
                _invalid("BAMF_C09_REGISTERED_SUPPORT_CONFLICT")
            supports[support.capability_id] = support
    return RequalificationLedger(tuple(sorted(
        supports.values(), key=lambda item: item.capability_id)))


def _install_fault(targets, fault, requalification=None) -> None:
    held = set(fault.held_artifact_ids)
    updated_support = {}
    if requalification is not None:
        updated_support = {
            item.capability_id: item
            for item in requalification.ledger.capabilities
        }
    for target in targets:
        owned = {
            node.artifact_id for node in getattr(target.owner, "index").nodes
        }.intersection(held)
        if owned:
            target.process_fault_holds.update(owned)
            setattr(
                target.owner, "_accepted_process_fault_holds",
                frozenset(target.process_fault_holds),
            )
            support = getattr(target.owner, "_support", None)
            if (support is not None
                    and getattr(support, "status", None)
                    is not RequalificationStatus.REQUALIFICATION_REQUIRED):
                setattr(
                    target.owner, "_support",
                    replace(
                        support,
                        status=RequalificationStatus.REQUALIFICATION_REQUIRED,
                    ),
                )
        capability_id = getattr(target.owner, "capability_id", None)
        support = updated_support.get(capability_id)
        if support is not None:
            setattr(target.owner, "_support", support)


def replay_stale_evidence(retained) -> tuple[object, ...]:
    """Rebuild durable stale-replay faults from accepted evidence and live owners."""
    if retained.registry is None:
        return ()
    records = read_records(retained.run_dir, retained.manifest_sha256)
    targets = tuple(retained.targets.values())
    for record in records:
        if record["event"] == PROCESS_FAULT_EVENT:
            _install_fault(targets, process_fault_from_record(record))

    index = _registered_index(targets)
    ledger = _registered_requalification(targets)
    if index is None or ledger is None:
        return ()
    corrections = {
        event.event_id: event
        for _event_id, event in accepted_corrections(
            retained.run_dir, retained.manifest_sha256, retained.registry)
    }
    remediations = tuple(
        remediation_from_record(record)
        for record in records if record["event"] == REMEDIATION_EVENT)
    claims = tuple(
        derived_claim_from_record(record)
        for record in records if record["event"] == DERIVED_CLAIM_EVENT)
    existing = {
        process_fault_from_record(record).offending_claim_id
        for record in records if record["event"] == PROCESS_FAULT_EVENT
    }
    results = []
    known_ids = {node.artifact_id for node in index.nodes}
    for remediation in remediations:
        correction = corrections.get(remediation.correction_event_id)
        if correction is None:
            continue
        for claim in claims:
            if claim.claim_id in existing or not set(claim.derived_path) <= known_ids:
                continue
            result = escalate_stale_replay(
                remediation, claim, correction, index, ledger, retained.registry)
            if result is None:
                continue
            record = process_fault_record(retained.manifest_sha256, result.fault)
            append_record(retained.run_dir, retained.manifest_sha256, record)
            _install_fault(targets, result.fault, result.requalification)
            existing.add(claim.claim_id)
            results.append(result)
    return tuple(results)


__all__ = ("replay_stale_evidence",)
