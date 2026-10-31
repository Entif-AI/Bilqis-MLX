"""Structural extraction from atlas_requalification.py; behavior preserved."""
from __future__ import annotations
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
import hashlib
import json
from ..semantics.cognitive_dependencies import DependencyRef
from .atlas_revalidation import CorrectionEvent, SourceAuthorityRegistry, _invalid, _name

CORRECTION_BRANCH_SCHEMA = "bilqis.c09.correction-branch/v1"

CORRECTION_BRANCHES_SCHEMA = "bilqis.c09.correction-branches/v1"

def _identity(value: object) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ).hexdigest()

def _canonical_names(names: object, *, nonempty: bool = True) -> bool:
    return (isinstance(names, tuple)
            and (bool(names) or not nonempty)
            and all(_name(item) for item in names)
            and names == tuple(sorted(set(names))))

@dataclass(frozen=True)
class CorrectionBranch:
    event: CorrectionEvent
    supersedes_event_ids: tuple[str, ...] = ()
    schema_version: str = CORRECTION_BRANCH_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.event, CorrectionEvent)
                or not _canonical_names(
                    self.supersedes_event_ids, nonempty=False)
                or self.event.event_id in self.supersedes_event_ids
                or self.schema_version != CORRECTION_BRANCH_SCHEMA):
            _invalid("BAMF_C09_CORRECTION_BRANCH_INVALID")

@dataclass(frozen=True)
class CorrectionBranches:
    dependency: DependencyRef
    branches: tuple[CorrectionBranch, ...]
    schema_version: str = CORRECTION_BRANCHES_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.dependency, DependencyRef)
                or not isinstance(self.branches, tuple)
                or any(not isinstance(branch, CorrectionBranch)
                       or branch.event.dependency != self.dependency
                       for branch in self.branches)
                or self.branches != tuple(sorted(
                    self.branches, key=lambda branch: branch.event.event_id))
                or len({branch.event.event_id for branch in self.branches})
                != len(self.branches)
                or self.schema_version != CORRECTION_BRANCHES_SCHEMA):
            _invalid("BAMF_C09_CORRECTION_BRANCHES_INVALID")
        identifiers = {branch.event.event_id for branch in self.branches}
        if any(not set(branch.supersedes_event_ids).issubset(identifiers)
               for branch in self.branches):
            _invalid("BAMF_C09_CORRECTION_SUPERSESSION_UNKNOWN")
        try:
            tuple(TopologicalSorter({
                branch.event.event_id: branch.supersedes_event_ids
                for branch in self.branches
            }).static_order())
        except CycleError:
            _invalid("BAMF_C09_CORRECTION_SUPERSESSION_CYCLE")

    @property
    def active(self) -> tuple[CorrectionBranch, ...]:
        superseded = {
            event_id for branch in self.branches
            for event_id in branch.supersedes_event_ids
        }
        return tuple(branch for branch in self.branches
                     if branch.event.event_id not in superseded)

def add_correction(
    branches: CorrectionBranches,
    event: CorrectionEvent,
    *,
    authority_registry: SourceAuthorityRegistry | None = None,
    supersedes_event_ids: tuple[str, ...] = (),
) -> CorrectionBranches:
    if (not isinstance(branches, CorrectionBranches)
            or not isinstance(event, CorrectionEvent)
            or event.dependency != branches.dependency):
        _invalid("BAMF_C09_CORRECTION_BRANCH_ARGUMENT_INVALID")
    if not isinstance(authority_registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
    authority_registry.verify_correction(event)
    if supersedes_event_ids != event.supersedes_event_ids:
        _invalid("BAMF_C09_UNSIGNED_SUPERSESSION")
    proposed = CorrectionBranch(event, event.supersedes_event_ids)
    prior = next((branch for branch in branches.branches
                  if branch.event.event_id == event.event_id), None)
    if prior is not None:
        if prior != proposed:
            _invalid("BAMF_C09_CORRECTION_EVENT_ID_CONFLICT")
        return branches
    return CorrectionBranches(
        branches.dependency,
        tuple(sorted((*branches.branches, proposed),
                     key=lambda branch: branch.event.event_id)),
    )
