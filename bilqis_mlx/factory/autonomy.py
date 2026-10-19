"""Deterministic, neural-inert planning for autonomous curriculum progress.

The planner answers one question: which source-valid semantic proof is missing
next?  It cannot train, score, admit, or mutate a student.  It consumes an
immutable :class:`FactoryRelease` plus evidence receipts and exposes the next
legal evidence target and the teacher options already authorized by that
release.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import FactoryRelease


class EvidenceKind(str, Enum):
    """Learner-facing proof families, distinct from source-generation hygiene."""

    DIRECT = "DIRECT"
    PREREQUISITE = "PREREQUISITE"
    COMPOSITION = "COMPOSITION"


@dataclass(frozen=True)
class EvidenceObligation:
    obligation_id: str
    capability_id: str
    kind: EvidenceKind
    key: str
    minimum_specimens: int
    generation_axes: tuple[str, ...]
    requires_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (not self.obligation_id or not self.capability_id or not self.key or
                not isinstance(self.kind, EvidenceKind) or
                type(self.minimum_specimens) is not int or self.minimum_specimens < 1 or
                not self.generation_axes or
                len(set(self.generation_axes)) != len(self.generation_axes) or
                any(not isinstance(item, str) or not item for item in self.generation_axes) or
                len(set(self.requires_capabilities)) != len(self.requires_capabilities) or
                any(not isinstance(item, str) or not item
                    for item in self.requires_capabilities)):
            raise ValueError("AUTONOMY_EVIDENCE_OBLIGATION_INVALID")


@dataclass(frozen=True)
class EvidenceReceipt:
    """One observed result for one obligation on one exact student/cohort."""

    obligation_id: str
    evidence_id: str
    checkpoint_sha256: str
    optimizer_step: int
    cohort_sha256: str
    specimen_count: int
    passed: bool

    def __post_init__(self) -> None:
        if not self.obligation_id or not self.evidence_id:
            raise ValueError("AUTONOMY_EVIDENCE_RECEIPT_IDENTITY_INVALID")
        for value, code in (
                (self.checkpoint_sha256, "AUTONOMY_EVIDENCE_CHECKPOINT_INVALID"),
                (self.cohort_sha256, "AUTONOMY_EVIDENCE_COHORT_INVALID")):
            if (not isinstance(value, str) or len(value) != 64 or
                    any(char not in "0123456789abcdef" for char in value)):
                raise ValueError(code)
        if (type(self.optimizer_step) is not int or self.optimizer_step < 0 or
                type(self.specimen_count) is not int or self.specimen_count < 1 or
                type(self.passed) is not bool):
            raise ValueError("AUTONOMY_EVIDENCE_RECEIPT_VALUE_INVALID")


@dataclass(frozen=True)
class EvidenceLedger:
    """Append-only evidence history bound to one immutable FactoryRelease."""

    factory_release_sha256: str
    receipts: tuple[EvidenceReceipt, ...] = ()

    def __post_init__(self) -> None:
        if (not isinstance(self.factory_release_sha256, str) or
                len(self.factory_release_sha256) != 64 or
                any(char not in "0123456789abcdef"
                    for char in self.factory_release_sha256) or
                any(not isinstance(item, EvidenceReceipt) for item in self.receipts) or
                len({item.evidence_id for item in self.receipts}) != len(self.receipts)):
            raise ValueError("AUTONOMY_EVIDENCE_LEDGER_INVALID")


@dataclass(frozen=True)
class CurriculumWorkItem:
    capability_id: str
    obligation: EvidenceObligation
    teaching_option_ids: tuple[str, ...]
    evidence_complete_prerequisites: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not self.capability_id or self.obligation.capability_id != self.capability_id or
                not self.teaching_option_ids or
                len(set(self.teaching_option_ids)) != len(self.teaching_option_ids)):
            raise ValueError("AUTONOMY_WORK_ITEM_INVALID")


def _capability_definitions(release: FactoryRelease):
    return {item.capability_id: item for item in release.capabilities}


def _course_capabilities(release: FactoryRelease):
    return release.course.capability_map


def _coverage_by_capability(release: FactoryRelease):
    return {item.capability_id: item for item in release.coverage_plans}


def obligations_for_capability(
    release: FactoryRelease, capability_id: str,
) -> tuple[EvidenceObligation, ...]:
    """Derive learner evidence obligations from immutable semantic structure.

    ``CoveragePlan.variation_axes`` constrain *how* witnesses must be generated;
    they are attached to every learner obligation but are not themselves claims
    the learner has to master.
    """
    release.verify()
    definition = _capability_definitions(release).get(capability_id)
    if definition is None:
        raise ValueError("AUTONOMY_UNKNOWN_CAPABILITY")
    coverage = _coverage_by_capability(release)[capability_id]
    declared = _course_capabilities(release)[capability_id]
    axes = coverage.variation_axes

    obligations = [EvidenceObligation(
        obligation_id=f"{capability_id}/direct",
        capability_id=capability_id,
        kind=EvidenceKind.DIRECT,
        key="source.direct",
        minimum_specimens=coverage.minimum_specimens,
        generation_axes=axes,
    )]
    obligations.extend(EvidenceObligation(
        obligation_id=f"{capability_id}/prerequisite/{predecessor}",
        capability_id=capability_id,
        kind=EvidenceKind.PREREQUISITE,
        key=predecessor,
        minimum_specimens=1,
        generation_axes=axes,
        requires_capabilities=(predecessor,),
    ) for predecessor in definition.prerequisites)
    obligations.extend(EvidenceObligation(
        obligation_id=f"{capability_id}/composition/{constituent}",
        capability_id=capability_id,
        kind=EvidenceKind.COMPOSITION,
        key=constituent,
        minimum_specimens=1,
        generation_axes=axes,
        requires_capabilities=(constituent,),
    ) for constituent in declared.composed_of)

    identities = tuple(item.obligation_id for item in obligations)
    if len(set(identities)) != len(identities):
        raise ValueError("AUTONOMY_DUPLICATE_EVIDENCE_OBLIGATION")
    return tuple(obligations)


def _obligation_map(release: FactoryRelease) -> dict[str, EvidenceObligation]:
    obligations = tuple(
        obligation
        for capability in release.capabilities
        for obligation in obligations_for_capability(release, capability.capability_id)
    )
    mapping = {item.obligation_id: item for item in obligations}
    if len(mapping) != len(obligations):
        raise ValueError("AUTONOMY_DUPLICATE_EVIDENCE_OBLIGATION")
    return mapping


def initial_evidence_ledger(release: FactoryRelease) -> EvidenceLedger:
    release.verify()
    return EvidenceLedger(release.release_sha256)


def _validate_ledger(
    release: FactoryRelease, ledger: EvidenceLedger,
) -> dict[str, EvidenceObligation]:
    if not isinstance(release, FactoryRelease) or not isinstance(ledger, EvidenceLedger):
        raise TypeError("AUTONOMY_INVALID_INPUT")
    if ledger.factory_release_sha256 != release.release_sha256:
        raise ValueError("AUTONOMY_RELEASE_MISMATCH")
    release.verify()
    obligations = _obligation_map(release)
    if any(item.obligation_id not in obligations for item in ledger.receipts):
        raise ValueError("AUTONOMY_UNKNOWN_EVIDENCE_OBLIGATION")
    return obligations


def _latest_receipts(ledger: EvidenceLedger) -> dict[str, EvidenceReceipt]:
    latest: dict[str, EvidenceReceipt] = {}
    for receipt in ledger.receipts:
        latest[receipt.obligation_id] = receipt
    return latest


def closed_obligations(
    release: FactoryRelease, ledger: EvidenceLedger,
) -> tuple[str, ...]:
    obligations = _validate_ledger(release, ledger)
    latest = _latest_receipts(ledger)
    return tuple(
        identity for identity in obligations
        if identity in latest and latest[identity].passed and
        latest[identity].specimen_count >= obligations[identity].minimum_specimens
    )


def evidence_complete_capabilities(
    release: FactoryRelease, ledger: EvidenceLedger,
) -> tuple[str, ...]:
    obligations = _validate_ledger(release, ledger)
    closed = set(closed_obligations(release, ledger))
    mastered: list[str] = []
    mastered_set: set[str] = set()
    for definition in release.capabilities:
        if not set(definition.prerequisites) <= mastered_set:
            continue
        required = {
            identity for identity, obligation in obligations.items()
            if obligation.capability_id == definition.capability_id
        }
        if required and required <= closed:
            mastered.append(definition.capability_id)
            mastered_set.add(definition.capability_id)
    return tuple(mastered)


def record_evidence(
    release: FactoryRelease, ledger: EvidenceLedger, receipt: EvidenceReceipt,
) -> EvidenceLedger:
    obligations = _validate_ledger(release, ledger)
    if not isinstance(receipt, EvidenceReceipt):
        raise TypeError("AUTONOMY_INVALID_EVIDENCE_RECEIPT")
    obligation = obligations.get(receipt.obligation_id)
    if obligation is None:
        raise ValueError("AUTONOMY_UNKNOWN_EVIDENCE_OBLIGATION")
    if receipt.passed and receipt.specimen_count < obligation.minimum_specimens:
        raise ValueError("AUTONOMY_INSUFFICIENT_EVIDENCE_SPECIMENS")
    if receipt.evidence_id in {item.evidence_id for item in ledger.receipts}:
        raise ValueError("AUTONOMY_DUPLICATE_EVIDENCE_RECEIPT")
    return EvidenceLedger(ledger.factory_release_sha256, (*ledger.receipts, receipt))


def _work_item(
    release: FactoryRelease, obligation: EvidenceObligation,
    mastered: tuple[str, ...],
) -> CurriculumWorkItem:
    definition = _capability_definitions(release)[obligation.capability_id]
    options = tuple(item.option_id for item in release.teaching_options
                    if item.capability_id == obligation.capability_id)
    return CurriculumWorkItem(
        capability_id=obligation.capability_id,
        obligation=obligation,
        teaching_option_ids=options,
        evidence_complete_prerequisites=tuple(
            item for item in mastered if item in definition.prerequisites),
    )


def next_work(
    release: FactoryRelease, ledger: EvidenceLedger,
) -> CurriculumWorkItem | None:
    """Return the next legal semantic proof target, never a training command."""
    obligations = _validate_ledger(release, ledger)
    latest = _latest_receipts(ledger)
    closed = set(closed_obligations(release, ledger))
    mastered = evidence_complete_capabilities(release, ledger)
    mastered_set = set(mastered)
    definitions = _capability_definitions(release)

    def eligible(obligation: EvidenceObligation) -> bool:
        definition = definitions[obligation.capability_id]
        return (obligation.obligation_id not in closed and
                set(definition.prerequisites) <= mastered_set and
                set(obligation.requires_capabilities) <= mastered_set)

    # A failed previously-attempted proof outranks new breadth.
    for receipt in reversed(ledger.receipts):
        if receipt.passed:
            continue
        obligation = obligations[receipt.obligation_id]
        if latest[receipt.obligation_id] == receipt and eligible(obligation):
            return _work_item(release, obligation, mastered)

    for definition in release.capabilities:
        if definition.capability_id in mastered_set:
            continue
        if not set(definition.prerequisites) <= mastered_set:
            continue
        for obligation in obligations_for_capability(release, definition.capability_id):
            if eligible(obligation):
                return _work_item(release, obligation, mastered)
    return None
