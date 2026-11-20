"""A09.5 adapter from pure atlas planning to the existing JIT proposal surface.

The adapter owns no source, staging, admission, or learning authority.  It binds
A09.1-A09.4 decisions to already verified Factory candidate artifacts and lets
the existing JIT gate re-check current learner evidence before emitting a
proposal.  Persisted staging and admission remain with their existing owners.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib

from bilqis_mlx.errors import BilqisError
from .autonomy import EvidenceLedger
from .candidate_frontier import CandidateFrontierRelease
from .candidate_staging import StagedCandidate
from .executable_release import ExecutableFactoryRelease
from .atlas_frontier_closure import FrontierClosure
from .atlas_frontier_contracts import CurriculumSnapshot, _fail
from .atlas_frontier_progress import (
    _counts, _direct_uncovered_count, _progress_result,
    _status_without_new_proposal, plan_frontier_progress,
)
from .atlas_frontier_progress_validation import (
    credited_obligation_keys,
    current_obligations,
    has_unrequested_ready,
)
from .atlas_frontier_progress_contracts import FrontierProgress
from . import candidate_realizations


_SHA256_HEX_LENGTH = hashlib.sha256().digest_size * 2
_OBLIGATION_KEY_PARTS = 2
_ACCEPTED_CREDIT_ISSUER = object()


def _digest(value: object) -> bool:
    return (type(value) is str and len(value) == _SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True)
class AcceptedObligationCredit:
    """Ephemeral planner capability minted only from authenticated B13 custody."""

    factory_release_sha256: str
    acceptance_sha256: str
    obligation_keys: tuple[tuple[str, str], ...]
    schema: str = "bilqis.factory-accepted-obligation-credit/v1"
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (getattr(self, "_issuance", None) is not _ACCEPTED_CREDIT_ISSUER
                or not _digest(self.factory_release_sha256)
                or not _digest(self.acceptance_sha256)
                or type(self.obligation_keys) is not tuple
                or self.obligation_keys != tuple(sorted(set(self.obligation_keys)))
                or any(type(item) is not tuple
                       or len(item) != _OBLIGATION_KEY_PARTS
                       or type(item[0]) is not str or not item[0]
                       or not _digest(item[1]) for item in self.obligation_keys)
                or self.schema != "bilqis.factory-accepted-obligation-credit/v1"):
            _fail("BAMF_PLANNER_ACCEPTED_CREDIT_INVALID")


def _issue_accepted_obligation_credit(
    factory_release_sha256: str,
    acceptance_sha256: str,
    obligation_keys: tuple[tuple[str, str], ...],
) -> AcceptedObligationCredit:
    """Mint planner credit after runtime has authenticated accepted B13 custody."""
    credit = object.__new__(AcceptedObligationCredit)
    for name, value in (
        ("factory_release_sha256", factory_release_sha256),
        ("acceptance_sha256", acceptance_sha256),
        ("obligation_keys", tuple(sorted(set(obligation_keys)))),
        ("schema", "bilqis.factory-accepted-obligation-credit/v1"),
        ("_issuance", _ACCEPTED_CREDIT_ISSUER),
    ):
        object.__setattr__(credit, name, value)
    credit.__post_init__()
    return credit


def plan_frontier_progress_with_accepted_credit(
    snapshot: CurriculumSnapshot, closure: FrontierClosure,
    accepted_credit: AcceptedObligationCredit, *,
    prior: FrontierProgress | None = None,
) -> FrontierProgress:
    """Project no-new-proposal status using authenticated accepted B13 credit."""
    accepted_credit.__post_init__()
    if accepted_credit.factory_release_sha256 != snapshot.admitted_factory_release_sha256:
        _fail("BAMF_PLANNER_ACCEPTED_CREDIT_RELEASE_DRIFT")
    current = current_obligations(closure)
    credited = (set() if prior is None else credited_obligation_keys(
        snapshot, closure, prior, current))
    credited.update(
        key for key in accepted_credit.obligation_keys
        if current.get(key[0]) == key[1])
    if has_unrequested_ready(closure, credited, current):
        _fail("BAMF_PLANNER_PROGRESS_SELECTION_REQUIRED")
    direct_uncovered = _direct_uncovered_count(snapshot)
    status = _status_without_new_proposal(
        snapshot, _counts(closure), credited, current,
        len(closure.source_holds), direct_uncovered)
    return _progress_result(
        snapshot, snapshot, closure, status, None, None, direct_uncovered, prior)


def bind_realized_snapshot(
    snapshot: CurriculumSnapshot,
    curriculum_candidate,
    candidate_frontier: CandidateFrontierRelease,
    current_release: ExecutableFactoryRelease,
    staged_candidates: tuple[StagedCandidate, ...],
) -> CurriculumSnapshot:
    """Overlay A09.5 realization evidence without changing the frozen A08 census."""
    if (type(snapshot) is not CurriculumSnapshot
            or snapshot.frozen_census_sha256 != curriculum_candidate.census.digest
            or snapshot.candidate_frontier_sha256 != candidate_frontier.release_sha256
            or snapshot.admitted_factory_release_sha256 != current_release.release_sha256):
        _fail("BAMF_PLANNER_REALIZATION_BRIDGE_INPUT_INVALID")
    coverage = candidate_realizations.realized_coverage_rows(
        curriculum_candidate, candidate_frontier, current_release, staged_candidates)
    frontier_edges = candidate_realizations.realized_prerequisite_edges(
        curriculum_candidate, candidate_frontier)
    edges = tuple(sorted(set((*snapshot.prerequisite_edges, *frontier_edges))))
    draft = replace(
        snapshot,
        coverage_rows=coverage,
        prerequisite_edges=edges,
        staged_factory_release_sha256s=tuple(sorted(
            item.successor.release_sha256 for item in staged_candidates)),
        snapshot_sha256="0" * 64,
    )
    result = replace(draft, snapshot_sha256=draft.expected_digest())
    result.verify()
    return result


@dataclass(frozen=True)
class AtlasCoverageEpoch:
    """Typed adapter view over existing authoritative artifacts, not new authority."""

    snapshot: CurriculumSnapshot
    closure: FrontierClosure
    candidate_frontier: CandidateFrontierRelease
    current_release: ExecutableFactoryRelease
    staged_candidates: tuple[StagedCandidate, ...]
    prior: FrontierProgress | None = None
    accepted_credit: AcceptedObligationCredit | None = None

    def verify(self) -> None:
        if (type(self.snapshot) is not CurriculumSnapshot
                or type(self.closure) is not FrontierClosure
                or type(self.candidate_frontier) is not CandidateFrontierRelease
                or not isinstance(self.current_release, ExecutableFactoryRelease)
                or type(self.staged_candidates) is not tuple
                or any(type(item) is not StagedCandidate for item in self.staged_candidates)
                or (self.prior is not None and type(self.prior) is not FrontierProgress)
                or (self.accepted_credit is not None
                    and type(self.accepted_credit) is not AcceptedObligationCredit)):
            _fail("BAMF_PLANNER_ADAPTER_INPUT_INVALID")
        self.snapshot.verify()
        self.closure.verify()
        self.candidate_frontier.verify()
        self.current_release.verify()
        if (self.closure.snapshot_sha256 != self.snapshot.snapshot_sha256
                or self.snapshot.candidate_frontier_sha256
                   != self.candidate_frontier.release_sha256
                or self.snapshot.admitted_factory_release_sha256
                   != self.current_release.release_sha256):
            _fail("BAMF_PLANNER_ADAPTER_EPOCH_MISMATCH")
        staged_sha256s = tuple(
            item.successor.release_sha256 for item in self.staged_candidates)
        if (len(set(staged_sha256s)) != len(staged_sha256s)
                or any(item not in self.snapshot.staged_factory_release_sha256s
                       for item in staged_sha256s)):
            _fail("BAMF_PLANNER_ADAPTER_STAGED_SET_INVALID")
        for item in self.staged_candidates:
            item.verify(self.candidate_frontier, self.current_release)
        if self.accepted_credit is not None:
            self.accepted_credit.__post_init__()
            if (self.accepted_credit.factory_release_sha256
                    != self.current_release.release_sha256):
                _fail("BAMF_PLANNER_ACCEPTED_CREDIT_RELEASE_DRIFT")
        if self.prior is not None:
            self.prior.verify()


@dataclass(frozen=True)
class AtlasLearnerEvidence:
    ledger: EvidenceLedger
    checkpoint_sha256: str
    optimizer_step: int

    def __post_init__(self) -> None:
        if (type(self.ledger) is not EvidenceLedger
                or type(self.checkpoint_sha256) is not str
                or len(self.checkpoint_sha256) != _SHA256_HEX_LENGTH
                or any(char not in "0123456789abcdef" for char in self.checkpoint_sha256)
                or type(self.optimizer_step) is not int or self.optimizer_step < 0):
            _fail("BAMF_PLANNER_ADAPTER_EVIDENCE_INVALID")
