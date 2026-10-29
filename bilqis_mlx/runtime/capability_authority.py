"""Pure uniform Factory preflight; source/run owners retain adoption authority."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Callable

from ..errors import BilqisError
from ..factory.assessment import AssessmentScopeContract, assessment_scope_contract
from ..factory.executable_release import ExecutableAdmissionReceipt, ExecutableFactoryRelease
from ..learning.capability_championship import ReplayBinding
from ..semantics.foundation.domains import contract_digest
from .capability_retention import Assessment, EvidenceKind, _invalid, _names, _sha


@dataclass(frozen=True)
class ReleasedEvidence:
    assessment: Assessment
    native_scope: AssessmentScopeContract
    policy_sha256: str
    source_family_ids: tuple[str, ...]
    expected_case_digest: str

    def __post_init__(self):
        if (not isinstance(self.assessment, Assessment)
                or not isinstance(self.native_scope, AssessmentScopeContract)
                or not _sha(self.policy_sha256) or not _sha(self.expected_case_digest)
                or not _names(self.source_family_ids) or not self.source_family_ids):
            _invalid("BAMF_RELEASED_EVIDENCE_INVALID")

    def verify(self, release):
        cohort = self.assessment.cohort
        capabilities = tuple(capability for capability, _ in cohort.capability_groups)
        expected = assessment_scope_contract(release, capabilities)
        groups = tuple((capability, release.execution_plan.capability_map[capability].grade_id)
                       for capability in expected.capabilities)
        if (expected != self.native_scope or groups != cohort.capability_groups
                or cohort.rubric_sha256 != expected.rubric_sha256
                or cohort.source_sha256 != expected.source_sha256
                or cohort.scope_sha256 != contract_digest(expected)
                or cohort.policy_sha256 != self.policy_sha256
                or tuple(sorted({case.source_family_id for case in cohort.cases}))
                != self.source_family_ids
                or cohort.expected_case_digest != self.expected_case_digest):
            _invalid("BAMF_RELEASED_EVIDENCE_CONTRACT_DRIFT")

    def digest(self):
        return contract_digest({"assessment": self.assessment.digest(), "scope": self.native_scope,
                                "policy": self.policy_sha256, "families": self.source_family_ids,
                                "case_census": self.expected_case_digest})


@dataclass(frozen=True)
class PrerequisiteThreshold:
    capability_id: str
    numerator: int
    denominator: int

    def __post_init__(self):
        if (not isinstance(self.capability_id, str) or not self.capability_id
                or type(self.numerator) is not int or type(self.denominator) is not int
                or not 0 < self.numerator <= self.denominator):
            _invalid("BAMF_PREREQUISITE_THRESHOLD_INVALID")


class AuthorityKind(str, Enum):
    SOURCE_RIGHTS = "SOURCE_RIGHTS"
    PROMOTION_POLICY = "PROMOTION_POLICY"
    ADMISSION_LEASE = "ADMISSION_LEASE"


class AuthorityStatus(str, Enum):
    PERMITTED = "PERMITTED"
    HELD = "HELD"


@dataclass(frozen=True)
class GateRequest:
    factory_release_sha256: str
    capability_id: str
    generation_digest: str
    checkpoint_sha256: str
    optimizer_step: int
    semantic_graph_sha256: str
    source_bindings_sha256: str
    policy_sha256: str
    evidence_sha256s: tuple[str, ...]
    prerequisite_thresholds: tuple[PrerequisiteThreshold, ...]
    measured_scores: tuple[tuple[str, int, int], ...]
    schema_version: str = "bilqis.c05.authority-request/v1"

    def digest(self):
        return contract_digest(self)


@dataclass(frozen=True)
class AuthorityReceipt:
    kind: AuthorityKind
    request_sha256: str
    authority_id: str
    status: AuthorityStatus
    reason: str
    schema_version: str = "bilqis.c05.authority-receipt/v1"

    def __post_init__(self):
        if (not isinstance(self.kind, AuthorityKind) or not _sha(self.request_sha256)
                or not isinstance(self.status, AuthorityStatus)
                or not all(isinstance(value, str) and value for value in (self.authority_id, self.reason))
                or self.schema_version != "bilqis.c05.authority-receipt/v1"):
            _invalid("BAMF_AUTHORITY_RECEIPT_INVALID")


class GateStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    HELD = "HELD"
    LEASE_REQUIRED = "LEASE_REQUIRED"


@dataclass(frozen=True)
class ProgressionGate:
    status: GateStatus
    reason: str
    request: GateRequest
    authorities: tuple[AuthorityReceipt, ...]
    blocked_prerequisites: tuple[str, ...] = ()
    schema_version: str = "bilqis.c05.progression-preflight/v1"


def evaluate_progression_authority(
        release, capability_id, target_evidence, prerequisite_evidence, current, *,
        admission, semantic_graph_sha256, prerequisite_thresholds,
        source_rights: Callable | None, promotion_policy: Callable | None,
        admission_lease: Callable | None) -> ProgressionGate:
    """Return fixture/requalification preflight; never publish an admission."""
    if (not isinstance(release, ExecutableFactoryRelease)
            or not isinstance(target_evidence, ReleasedEvidence)
            or not isinstance(prerequisite_evidence, tuple)
            or any(not isinstance(item, ReleasedEvidence) for item in prerequisite_evidence)
            or not isinstance(current, ReplayBinding) or not _sha(semantic_graph_sha256)
            or not isinstance(prerequisite_thresholds, tuple)
            or any(not isinstance(item, PrerequisiteThreshold) for item in prerequisite_thresholds)):
        _invalid("BAMF_PROGRESSION_PREFLIGHT_INPUT_INVALID")
    release.verify()
    definitions = release.execution_plan.capability_map
    if capability_id not in definitions:
        _invalid("BAMF_PROGRESSION_CAPABILITY_NOT_RELEASED")
    if current.verify_generation(current.generation_digest, current.checkpoint) is not True:
        _invalid("BAMF_PROGRESSION_GENERATION_UNVERIFIED")
    inputs = (target_evidence, *prerequisite_evidence)
    for item in inputs:
        item.verify(release)
        if (item.assessment.generation_digest != current.generation_digest
                or item.policy_sha256 != target_evidence.policy_sha256
                or not set(item.assessment.solver_contracts) <= set(current.solver_contracts)):
            _invalid("BAMF_PROGRESSION_EVIDENCE_GENERATION_OR_POLICY_DRIFT")
    if capability_id not in dict(target_evidence.assessment.cohort.capability_groups):
        _invalid("BAMF_PROGRESSION_TARGET_EVIDENCE_ABSENT")
    required = set()
    pending = list(definitions[capability_id].prerequisites)
    while pending:
        prerequisite = pending.pop()
        if prerequisite not in required:
            required.add(prerequisite)
            pending.extend(definitions[prerequisite].prerequisites)
    thresholds = {item.capability_id: Fraction(item.numerator, item.denominator)
                  for item in prerequisite_thresholds}
    if len(thresholds) != len(prerequisite_thresholds) or set(thresholds) != required:
        _invalid("BAMF_PROGRESSION_PREREQUISITE_POLICY_CENSUS_DRIFT")
    scores = {}
    for item in inputs:
        for capability, _ in item.assessment.cohort.capability_groups:
            value = item.assessment.score(capability)
            if capability in scores and scores[capability] != value:
                _invalid("BAMF_PROGRESSION_CONFLICTING_CURRENT_EVIDENCE")
            scores[capability] = value
    request = GateRequest(
        release.release_sha256, capability_id, current.generation_digest,
        current.checkpoint.sha256, current.checkpoint.optimizer_step, semantic_graph_sha256,
        release.source_bindings.digest(), target_evidence.policy_sha256,
        tuple(item.digest() for item in inputs), prerequisite_thresholds,
        tuple((capability, *score) for capability, score in sorted(scores.items())))
    authorities = []
    def held(reason, blocked=(), status=GateStatus.HELD):
        return ProgressionGate(status, reason, request, tuple(authorities), blocked)
    if not isinstance(admission, ExecutableAdmissionReceipt):
        return held("FACTORY_ADMISSION_REQUIRED")
    try:
        admission.verify(release)
        admission.verify_baseline(student_sha256=current.checkpoint.sha256,
                                  optimizer_step=current.checkpoint.optimizer_step,
                                  semantic_graph_sha256=semantic_graph_sha256)
    except ValueError:
        return held("FACTORY_ADMISSION_INVALID")
    if target_evidence.assessment.cohort.kind not in (EvidenceKind.FRESH_TARGET, EvidenceKind.FRESH_LESSON):
        return held("INDEPENDENT_FRESH_TARGET_EVIDENCE_REQUIRED")
    for kind, verifier in ((AuthorityKind.SOURCE_RIGHTS, source_rights),
                           (AuthorityKind.PROMOTION_POLICY, promotion_policy),
                           (AuthorityKind.ADMISSION_LEASE, admission_lease)):
        status = GateStatus.LEASE_REQUIRED if kind is AuthorityKind.ADMISSION_LEASE else GateStatus.HELD
        if verifier is None:
            return held(kind.value + "_AUTHORITY_REQUIRED", status=status)
        try:
            receipt = verifier(request)
        except (BilqisError, ValueError, TypeError):
            return held(kind.value + "_AUTHORITY_REJECTED", status=status)
        if (not isinstance(receipt, AuthorityReceipt) or receipt.kind is not kind
                or receipt.request_sha256 != request.digest()):
            return held(kind.value + "_RECEIPT_DRIFT", status=status)
        authorities.append(receipt)
        if receipt.status is not AuthorityStatus.PERMITTED:
            return held(kind.value + "_AUTHORITY_HELD", status=status)
    blocked = tuple(sorted(capability for capability in required
                           if capability not in scores
                           or Fraction(*scores[capability]) < thresholds[capability]))
    if blocked:
        return held("PREREQUISITE_EVIDENCE_INSUFFICIENT", blocked)
    return ProgressionGate(GateStatus.ELIGIBLE, "UNIFORM_FACTORY_PREFLIGHT_PASSED",
                           request, tuple(authorities))
