"""Deterministic, neural-inert planning for autonomous curriculum progress.

The planner answers one question: which source-valid semantic proof is missing
next?  It cannot train, score, admit, or mutate a student.  It consumes an
immutable :class:`FactoryRelease` plus evidence receipts and exposes the next
legal evidence target and the teacher options already authorized by that
release.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json

from .model import CapabilityDefinition, CoveragePlan, FactoryRelease


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class SourceCompositionEdge:
    consumer: str
    producer: str
    operand_slot: int
    witness_ids: tuple[str, ...]
    source_cohort_sha256: str

    def __post_init__(self) -> None:
        if (not self.consumer or not self.producer or
                type(self.operand_slot) is not int or self.operand_slot < 0 or
                not self.witness_ids or len(set(self.witness_ids)) != len(self.witness_ids) or
                any(not isinstance(item, str) or not item for item in self.witness_ids) or
                not isinstance(self.source_cohort_sha256, str) or
                len(self.source_cohort_sha256) != 64 or
                any(char not in "0123456789abcdef" for char in self.source_cohort_sha256)):
            raise ValueError("AUTONOMY_SOURCE_COMPOSITION_EDGE_INVALID")


@dataclass(frozen=True)
class ProjectionEvidenceSpec:
    """One source-supported learner-proof projection bound into a plan."""

    capability_id: str
    projection_id: str
    minimum_specimens: int
    proof_axes: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.capability_id, str) or not self.capability_id or
                not isinstance(self.projection_id, str) or not self.projection_id or
                type(self.minimum_specimens) is not int or
                self.minimum_specimens < 1 or not self.proof_axes or
                len(set(self.proof_axes)) != len(self.proof_axes) or
                any(not isinstance(item, str) or not item
                    for item in self.proof_axes)):
            raise ValueError("AUTONOMY_PROJECTION_EVIDENCE_SPEC_INVALID")


@dataclass(frozen=True)
class SupplementalEvidenceSpec:
    """Provider-owned proof dependency that does not rewrite Course semantics."""

    capability_id: str
    kind: str
    key: str
    requires_capabilities: tuple[str, ...]
    minimum_specimens: int = 1

    def __post_init__(self) -> None:
        if (not isinstance(self.capability_id, str) or not self.capability_id or
                self.kind not in {"PREREQUISITE", "COMPOSITION"} or
                not isinstance(self.key, str) or not self.key or
                not self.requires_capabilities or
                len(set(self.requires_capabilities)) !=
                len(self.requires_capabilities) or
                any(not isinstance(item, str) or not item
                    for item in self.requires_capabilities) or
                type(self.minimum_specimens) is not int or
                self.minimum_specimens < 1):
            raise ValueError("AUTONOMY_SUPPLEMENTAL_EVIDENCE_SPEC_INVALID")


@dataclass(frozen=True)
class AutonomyPlan:
    factory_release_sha256: str
    source_composition_audited: bool
    source_composition_edges: tuple[SourceCompositionEdge, ...] = ()
    coverage_debt: tuple[str, ...] = ()
    blocked_capabilities: tuple[str, ...] = ()
    deferred_composition_candidates: tuple[str, ...] = ()
    projection_evidence: tuple[ProjectionEvidenceSpec, ...] = ()
    supplemental_evidence: tuple[SupplementalEvidenceSpec, ...] = ()
    remediation_failure_limit: int = 3

    def __post_init__(self) -> None:
        if (not isinstance(self.factory_release_sha256, str) or
                len(self.factory_release_sha256) != 64 or
                any(char not in "0123456789abcdef" for char in self.factory_release_sha256) or
                type(self.source_composition_audited) is not bool or
                any(not isinstance(item, SourceCompositionEdge)
                    for item in self.source_composition_edges) or
                len(set(self.coverage_debt)) != len(self.coverage_debt) or
                any(not isinstance(item, str) or not item for item in self.coverage_debt) or
                len(set(self.blocked_capabilities)) != len(self.blocked_capabilities) or
                any(not isinstance(item, str) or not item
                    for item in self.blocked_capabilities) or
                len(set(self.deferred_composition_candidates)) !=
                len(self.deferred_composition_candidates) or
                any(not isinstance(item, str) or not item
                    for item in self.deferred_composition_candidates) or
                any(not isinstance(item, ProjectionEvidenceSpec)
                    for item in self.projection_evidence) or
                len({(item.capability_id, item.projection_id)
                     for item in self.projection_evidence}) !=
                len(self.projection_evidence) or
                any(not isinstance(item, SupplementalEvidenceSpec)
                    for item in self.supplemental_evidence) or
                len({(item.capability_id, item.kind, item.key)
                     for item in self.supplemental_evidence}) !=
                len(self.supplemental_evidence) or
                type(self.remediation_failure_limit) is not int or
                self.remediation_failure_limit < 1):
            raise ValueError("AUTONOMY_PLAN_INVALID")

    def digest(self) -> str:
        payload = asdict(self)
        # Preserve all existing v1 plan identities when no projection contract
        # has been attached. Old durable autonomy snapshots therefore remain
        # readable without a state migration merely because this capability
        # was added.
        if not self.projection_evidence:
            payload.pop("projection_evidence", None)
        if not self.supplemental_evidence:
            payload.pop("supplemental_evidence", None)
        if self.remediation_failure_limit == 3:
            payload.pop("remediation_failure_limit", None)
        return _digest(payload)


def is_factory_release(release) -> bool:
    from .executable_release import ExecutableFactoryRelease
    return isinstance(release, (FactoryRelease, ExecutableFactoryRelease))


def release_capabilities(release):
    """Project autonomy facts from the admitted executable plan or historical v1."""
    if isinstance(release, FactoryRelease):
        return release.capabilities
    return tuple(CapabilityDefinition(
        item.capability_id, item.grade_id, item.prerequisites,
        item.provider_id, item.oracle_id,
        tuple(family.kind for family in item.answer_families))
        for item in release.execution_plan.capabilities)


def compile_autonomy_plan(
    release: FactoryRelease, composition_report: dict | None = None,
    *, projection_evidence: tuple[ProjectionEvidenceSpec, ...] = (),
    projection_coverage_debt: tuple[str, ...] = (),
    supplemental_evidence: tuple[SupplementalEvidenceSpec, ...] = (),
    remediation_failure_limit: int = 3,
) -> AutonomyPlan:
    """Bind learner planning to verified typed composition coverage when present.

    Type-compatible edges are not learner work until a source adapter has
    discharged the semantic-coverage debt.  Unresolved or partially witnessed
    consumers remain explicitly blocked instead of being silently omitted.
    """
    release.verify()
    capability_ids = tuple(item.capability_id for item in release_capabilities(release))
    if (type(remediation_failure_limit) is not int or
            remediation_failure_limit < 1 or
            any(not isinstance(item, ProjectionEvidenceSpec)
            for item in projection_evidence) or
            len({(item.capability_id, item.projection_id)
                 for item in projection_evidence}) != len(projection_evidence) or
            any(item.capability_id not in capability_ids
                for item in projection_evidence) or
            len(set(projection_coverage_debt)) != len(projection_coverage_debt) or
            any(not isinstance(item, str) or not item
                for item in projection_coverage_debt)):
        raise ValueError("AUTONOMY_PROJECTION_EVIDENCE_SCOPE_INVALID")
    if (any(not isinstance(item, SupplementalEvidenceSpec)
            for item in supplemental_evidence) or
            len({(item.capability_id, item.kind, item.key)
                 for item in supplemental_evidence}) !=
            len(supplemental_evidence) or
            any(item.capability_id not in capability_ids or
                not set(item.requires_capabilities) <= set(capability_ids)
                for item in supplemental_evidence)):
        raise ValueError("AUTONOMY_SUPPLEMENTAL_EVIDENCE_SCOPE_INVALID")
    projection_blocked = set()
    for item in projection_coverage_debt:
        capability = item.split(":", 1)[0]
        if capability not in capability_ids:
            raise ValueError("AUTONOMY_PROJECTION_COVERAGE_DEBT_SCOPE_INVALID")
        projection_blocked.add(capability)
    if composition_report is None:
        return AutonomyPlan(
            release.release_sha256,
            False,
            coverage_debt=projection_coverage_debt,
            blocked_capabilities=tuple(
                item for item in capability_ids if item in projection_blocked),
            projection_evidence=projection_evidence,
            supplemental_evidence=supplemental_evidence,
        )
    from ..curriculum_compiler import compile_ast
    from ..semantic_coverage import SCHEMA

    if (not isinstance(composition_report, dict) or
            composition_report.get("schema") != SCHEMA or
            composition_report.get("ast_sha256") != compile_ast(release.course).digest()):
        raise ValueError("AUTONOMY_COMPOSITION_REPORT_BINDING_INVALID")
    if set(composition_report.get("capabilities", ())) != set(capability_ids):
        raise ValueError("AUTONOMY_COMPOSITION_REPORT_SCOPE_INVALID")

    source_cohort = composition_report.get("source_witness_cohort_sha256")
    edges = []
    debt = list(projection_coverage_debt)
    blocked = set(projection_blocked)
    deferred = []
    for unresolved in composition_report.get("unresolved", ()):
        capability = unresolved.get("capability") if isinstance(unresolved, dict) else None
        failure = unresolved.get("failure") if isinstance(unresolved, dict) else None
        if not capability or capability not in capability_ids or not failure:
            raise ValueError("AUTONOMY_COMPOSITION_REPORT_UNRESOLVED_INVALID")
        # Typed discovery is advisory.  Multi-root, inverse, and domain-level
        # capabilities may have explicit factory dependencies that the generic
        # signature projection cannot represent.  Preserve that diagnostic
        # without turning parser incompleteness into learner debt.
        deferred.append(f"{capability}:UNRESOLVED:{failure}")

    for raw in composition_report.get("obligations", ()):
        if not isinstance(raw, dict):
            raise ValueError("AUTONOMY_COMPOSITION_REPORT_EDGE_INVALID")
        consumer, producer = raw.get("consumer"), raw.get("producer")
        slot, status = raw.get("operand_slot"), raw.get("status")
        if (consumer not in capability_ids or producer not in capability_ids or
                type(slot) is not int or slot < 0 or not status):
            raise ValueError("AUTONOMY_COMPOSITION_REPORT_EDGE_INVALID")
        covered = status == "SOURCE_CONTRAST_COVERED" and not raw.get("coverage_debt", True)
        if covered:
            edges.append(SourceCompositionEdge(
                consumer=consumer, producer=producer, operand_slot=slot,
                witness_ids=tuple(raw.get("witness_ids", ())),
                source_cohort_sha256=source_cohort,
            ))
        elif not raw.get("declared_prerequisite", False):
            # Type compatibility is only a candidate composition edge.  Until
            # source evidence or an explicit semantic declaration elevates it,
            # keep it visible but do not block the learner on speculative debt.
            deferred.append(f"{consumer}:{producer}:{slot}:{status}")
        else:
            debt.append(f"{consumer}:{producer}:{slot}:{status}")
            blocked.add(consumer)
    edges = sorted(edges, key=lambda item: (item.consumer, item.producer, item.operand_slot))
    deferred = list(dict.fromkeys(deferred))
    return AutonomyPlan(
        release.release_sha256, True, tuple(edges), tuple(debt),
        tuple(item for item in capability_ids if item in blocked),
        tuple(deferred),
        projection_evidence,
        supplemental_evidence,
        remediation_failure_limit,
    )


def next_source_coverage_debt(plan: AutonomyPlan) -> str | None:
    if not isinstance(plan, AutonomyPlan):
        raise TypeError("AUTONOMY_INVALID_PLAN")
    return plan.coverage_debt[0] if plan.coverage_debt else None


def _resolve_plan(release: FactoryRelease, plan: AutonomyPlan | None) -> AutonomyPlan:
    resolved = compile_autonomy_plan(release) if plan is None else plan
    if not isinstance(resolved, AutonomyPlan):
        raise TypeError("AUTONOMY_INVALID_PLAN")
    if resolved.factory_release_sha256 != release.release_sha256:
        raise ValueError("AUTONOMY_PLAN_RELEASE_MISMATCH")
    return resolved


class EvidenceKind(str, Enum):
    """Learner-facing proof families, distinct from source-generation hygiene."""

    DIRECT = "DIRECT"
    PREREQUISITE = "PREREQUISITE"
    COMPOSITION = "COMPOSITION"
    PROJECTION = "PROJECTION"


@dataclass(frozen=True)
class EvidenceObligation:
    obligation_id: str
    capability_id: str
    kind: EvidenceKind
    key: str
    minimum_specimens: int
    generation_axes: tuple[str, ...]
    requires_capabilities: tuple[str, ...] = ()
    proof_axes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (not self.obligation_id or not self.capability_id or not self.key or
                not isinstance(self.kind, EvidenceKind) or
                type(self.minimum_specimens) is not int or self.minimum_specimens < 1 or
                not self.generation_axes or
                len(set(self.generation_axes)) != len(self.generation_axes) or
                any(not isinstance(item, str) or not item for item in self.generation_axes) or
                len(set(self.requires_capabilities)) != len(self.requires_capabilities) or
                any(not isinstance(item, str) or not item
                    for item in self.requires_capabilities) or
                len(set(self.proof_axes)) != len(self.proof_axes) or
                any(not isinstance(item, str) or not item
                    for item in self.proof_axes)):
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
class TeachingReceipt:
    """One bounded teaching intervention after one failed evidence receipt."""

    obligation_id: str
    intervention_id: str
    teaching_option_id: str
    parent_checkpoint_sha256: str
    parent_optimizer_step: int
    checkpoint_sha256: str
    optimizer_step: int
    # These fields are optional only so historical snapshots remain readable.
    # New interventions are rejected by record_teaching_intervention unless all
    # provenance is present and bound to the released construction boundary.
    selected_provider_id: str | None = None
    provider_implementation_sha256: str | None = None
    specimen_ids: tuple[str, ...] = ()
    specimen_content_sha256: str | None = None
    variation_axes: tuple[str, ...] = ()
    optimizer_step_delta: int | None = None

    def __post_init__(self) -> None:
        # JSON state decoding yields lists; normalize them back to the durable
        # tuple form before validating or comparing the released contract.
        if (not isinstance(self.specimen_ids, (tuple, list)) or
                not isinstance(self.variation_axes, (tuple, list))):
            raise ValueError("AUTONOMY_TEACHING_RECEIPT_PROVENANCE_INVALID")
        object.__setattr__(self, "specimen_ids", tuple(self.specimen_ids))
        object.__setattr__(self, "variation_axes", tuple(self.variation_axes))
        if (not self.obligation_id or not self.intervention_id or
                not self.teaching_option_id):
            raise ValueError("AUTONOMY_TEACHING_RECEIPT_IDENTITY_INVALID")
        for value in (self.parent_checkpoint_sha256, self.checkpoint_sha256):
            if (not isinstance(value, str) or len(value) != 64 or
                    any(char not in "0123456789abcdef" for char in value)):
                raise ValueError("AUTONOMY_TEACHING_RECEIPT_CHECKPOINT_INVALID")
        if (type(self.parent_optimizer_step) is not int or
                type(self.optimizer_step) is not int or
                self.parent_optimizer_step < 0 or
                self.optimizer_step <= self.parent_optimizer_step or
                self.checkpoint_sha256 == self.parent_checkpoint_sha256):
            raise ValueError("AUTONOMY_TEACHING_RECEIPT_NO_CHECKPOINT_PROGRESS")
        if self.optimizer_step_delta is not None and (
                type(self.optimizer_step_delta) is not int or
                self.optimizer_step_delta < 1 or
                self.optimizer_step_delta !=
                self.optimizer_step - self.parent_optimizer_step):
            raise ValueError("AUTONOMY_TEACHING_RECEIPT_STEP_DELTA_INVALID")
        if ((self.selected_provider_id is not None and
             (not isinstance(self.selected_provider_id, str) or
              not self.selected_provider_id)) or
                (self.provider_implementation_sha256 is not None and
                 (not isinstance(self.provider_implementation_sha256, str) or
                  len(self.provider_implementation_sha256) != 64 or
                  any(char not in "0123456789abcdef"
                      for char in self.provider_implementation_sha256))) or
                len(set(self.specimen_ids)) != len(self.specimen_ids) or
                any(not isinstance(item, str) or not item
                    for item in self.specimen_ids) or
                (self.specimen_content_sha256 is not None and
                 (not isinstance(self.specimen_content_sha256, str) or
                  len(self.specimen_content_sha256) != 64 or
                  any(char not in "0123456789abcdef"
                      for char in self.specimen_content_sha256))) or
                len(set(self.variation_axes)) != len(self.variation_axes) or
                any(not isinstance(item, str) or not item
                    for item in self.variation_axes)):
            raise ValueError("AUTONOMY_TEACHING_RECEIPT_PROVENANCE_INVALID")


@dataclass(frozen=True)
class RejectedTeachingAttemptReceipt:
    """One source-grounded teaching attempt that did not advance custody."""

    obligation_id: str
    parent_evidence_id: str
    attempt_id: str
    teaching_option_id: str
    retained_checkpoint_sha256: str
    retained_optimizer_step: int
    candidate_optimizer_step: int
    retention_reason: str
    selected_provider_id: str
    provider_implementation_sha256: str
    specimen_content_sha256: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (
                self.obligation_id, self.parent_evidence_id, self.attempt_id,
                self.teaching_option_id, self.retention_reason,
                self.selected_provider_id)):
            raise ValueError("AUTONOMY_REJECTED_ATTEMPT_IDENTITY_INVALID")
        for value in (
                self.retained_checkpoint_sha256,
                self.provider_implementation_sha256,
                self.specimen_content_sha256):
            if (not isinstance(value, str) or len(value) != 64 or
                    any(char not in "0123456789abcdef" for char in value)):
                raise ValueError("AUTONOMY_REJECTED_ATTEMPT_DIGEST_INVALID")
        if (type(self.retained_optimizer_step) is not int or
                type(self.candidate_optimizer_step) is not int or
                self.retained_optimizer_step < 0 or
                self.candidate_optimizer_step <= self.retained_optimizer_step):
            raise ValueError("AUTONOMY_REJECTED_ATTEMPT_STEP_INVALID")


@dataclass(frozen=True)
class EvidenceLedger:
    """Append-only evidence history bound to one release and autonomy plan."""

    factory_release_sha256: str
    autonomy_plan_sha256: str
    receipts: tuple[EvidenceReceipt, ...] = ()
    interventions: tuple[TeachingReceipt, ...] = ()
    rejected_attempts: tuple[RejectedTeachingAttemptReceipt, ...] = ()

    def __post_init__(self) -> None:
        if (not isinstance(self.factory_release_sha256, str) or
                len(self.factory_release_sha256) != 64 or
                any(char not in "0123456789abcdef"
                    for char in self.factory_release_sha256) or
                not isinstance(self.autonomy_plan_sha256, str) or
                len(self.autonomy_plan_sha256) != 64 or
                any(char not in "0123456789abcdef"
                    for char in self.autonomy_plan_sha256) or
                any(not isinstance(item, EvidenceReceipt) for item in self.receipts) or
                len({item.evidence_id for item in self.receipts}) != len(self.receipts) or
                any(not isinstance(item, TeachingReceipt) for item in self.interventions) or
                len({item.intervention_id for item in self.interventions}) !=
                len(self.interventions) or
                any(not isinstance(item, RejectedTeachingAttemptReceipt)
                    for item in self.rejected_attempts) or
                len({item.attempt_id for item in self.rejected_attempts}) !=
                len(self.rejected_attempts)):
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


@dataclass(frozen=True)
class TeachingWorkItem:
    capability_id: str
    obligation: EvidenceObligation
    teaching_option_ids: tuple[str, ...]
    failed_evidence: EvidenceReceipt

    def __post_init__(self) -> None:
        if (not self.capability_id or
                self.obligation.capability_id != self.capability_id or
                self.failed_evidence.obligation_id != self.obligation.obligation_id or
                not self.teaching_option_ids or
                len(set(self.teaching_option_ids)) != len(self.teaching_option_ids)):
            raise ValueError("AUTONOMY_TEACHING_WORK_ITEM_INVALID")


def _capability_definitions(release: FactoryRelease):
    return {item.capability_id: item for item in release_capabilities(release)}


def _course_capabilities(release: FactoryRelease):
    return (release.course.capability_map if isinstance(release, FactoryRelease)
            else release.execution_plan.capability_map)


def _coverage_by_capability(release: FactoryRelease):
    if isinstance(release, FactoryRelease):
        return {item.capability_id: item for item in release.coverage_plans}
    return {item.capability_id: CoveragePlan(
        item.capability_id, item.variation_axes, item.exam_item_count)
        for item in release.execution_plan.capabilities}


def obligations_for_capability(
    release: FactoryRelease, capability_id: str, *, plan: AutonomyPlan | None = None,
) -> tuple[EvidenceObligation, ...]:
    """Derive learner evidence obligations from immutable semantic structure.

    ``CoveragePlan.variation_axes`` constrain *how* witnesses must be generated;
    they are attached to every learner obligation but are not themselves claims
    the learner has to master.
    """
    release.verify()
    resolved_plan = _resolve_plan(release, plan)
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
        obligation_id=(
            f"{capability_id}/projection/{projection.projection_id}"),
        capability_id=capability_id,
        kind=EvidenceKind.PROJECTION,
        key=projection.projection_id,
        minimum_specimens=projection.minimum_specimens,
        generation_axes=axes,
        proof_axes=projection.proof_axes,
    ) for projection in resolved_plan.projection_evidence
      if projection.capability_id == capability_id)
    obligations.extend(EvidenceObligation(
        obligation_id=(
            f"{capability_id}/supplemental/{item.kind.lower()}/{item.key}"),
        capability_id=capability_id,
        kind=(EvidenceKind.PREREQUISITE
              if item.kind == "PREREQUISITE"
              else EvidenceKind.COMPOSITION),
        key=item.key,
        minimum_specimens=item.minimum_specimens,
        generation_axes=axes,
        requires_capabilities=item.requires_capabilities,
    ) for item in resolved_plan.supplemental_evidence
      if item.capability_id == capability_id)
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
    if resolved_plan.source_composition_audited:
        obligations.extend(EvidenceObligation(
            obligation_id=(f"{capability_id}/typed-composition/{edge.producer}/"
                           f"slot/{edge.operand_slot}"),
            capability_id=capability_id,
            kind=EvidenceKind.COMPOSITION,
            key=f"{edge.producer}@{edge.operand_slot}",
            minimum_specimens=1,
            generation_axes=axes,
            requires_capabilities=(edge.producer,),
        ) for edge in resolved_plan.source_composition_edges
          if edge.consumer == capability_id)

    identities = tuple(item.obligation_id for item in obligations)
    if len(set(identities)) != len(identities):
        raise ValueError("AUTONOMY_DUPLICATE_EVIDENCE_OBLIGATION")
    return tuple(obligations)


def _obligation_map(
    release: FactoryRelease, plan: AutonomyPlan | None = None,
) -> dict[str, EvidenceObligation]:
    obligations = tuple(
        obligation
        for capability in release_capabilities(release)
        for obligation in obligations_for_capability(
            release, capability.capability_id, plan=plan)
    )
    mapping = {item.obligation_id: item for item in obligations}
    if len(mapping) != len(obligations):
        raise ValueError("AUTONOMY_DUPLICATE_EVIDENCE_OBLIGATION")
    return mapping


def initial_evidence_ledger(
    release: FactoryRelease, *, plan: AutonomyPlan | None = None,
) -> EvidenceLedger:
    release.verify()
    resolved_plan = _resolve_plan(release, plan)
    return EvidenceLedger(release.release_sha256, resolved_plan.digest())


def _validate_ledger(
    release: FactoryRelease, ledger: EvidenceLedger, *, plan: AutonomyPlan | None = None,
) -> dict[str, EvidenceObligation]:
    if not is_factory_release(release) or not isinstance(ledger, EvidenceLedger):
        raise TypeError("AUTONOMY_INVALID_INPUT")
    if ledger.factory_release_sha256 != release.release_sha256:
        raise ValueError("AUTONOMY_RELEASE_MISMATCH")
    resolved_plan = _resolve_plan(release, plan)
    if ledger.autonomy_plan_sha256 != resolved_plan.digest():
        raise ValueError("AUTONOMY_PLAN_MISMATCH")
    release.verify()
    obligations = _obligation_map(release, resolved_plan)
    if any(item.obligation_id not in obligations for item in ledger.receipts):
        raise ValueError("AUTONOMY_UNKNOWN_EVIDENCE_OBLIGATION")
    if any(
            item.obligation_id not in obligations
            for item in (*ledger.interventions, *ledger.rejected_attempts)):
        raise ValueError("AUTONOMY_UNKNOWN_EVIDENCE_OBLIGATION")
    return obligations


def _latest_receipts(ledger: EvidenceLedger) -> dict[str, EvidenceReceipt]:
    latest: dict[str, EvidenceReceipt] = {}
    for receipt in ledger.receipts:
        latest[receipt.obligation_id] = receipt
    return latest


def _latest_interventions(ledger: EvidenceLedger) -> dict[str, TeachingReceipt]:
    latest: dict[str, TeachingReceipt] = {}
    for receipt in ledger.interventions:
        latest[receipt.obligation_id] = receipt
    return latest


def _validate_current_context(
    checkpoint_sha256: str | None, optimizer_step: int | None,
) -> tuple[str, int] | None:
    """Validate an explicit causal checkpoint context, if a caller supplies one."""
    if checkpoint_sha256 is None and optimizer_step is None:
        return None
    if (not isinstance(checkpoint_sha256, str) or len(checkpoint_sha256) != 64 or
            any(char not in "0123456789abcdef" for char in checkpoint_sha256) or
            type(optimizer_step) is not int or optimizer_step < 0):
        raise ValueError("AUTONOMY_CURRENT_CHECKPOINT_CONTEXT_INVALID")
    return checkpoint_sha256, optimizer_step


def _receipt_is_current(
    receipt: EvidenceReceipt, current: tuple[str, int] | None,
) -> bool:
    return current is None or (
        receipt.checkpoint_sha256 == current[0] and
        receipt.optimizer_step == current[1])


def closed_obligations(
    release: FactoryRelease, ledger: EvidenceLedger, *, plan: AutonomyPlan | None = None,
    current_checkpoint_sha256: str | None = None,
    current_optimizer_step: int | None = None,
) -> tuple[str, ...]:
    obligations = _validate_ledger(release, ledger, plan=plan)
    current = _validate_current_context(
        current_checkpoint_sha256, current_optimizer_step)
    latest = _latest_receipts(ledger)
    return tuple(
        identity for identity in obligations
        if identity in latest and latest[identity].passed and
        latest[identity].specimen_count >= obligations[identity].minimum_specimens and
        _receipt_is_current(latest[identity], current)
    )


def evidence_complete_capabilities(
    release: FactoryRelease, ledger: EvidenceLedger, *, plan: AutonomyPlan | None = None,
    current_checkpoint_sha256: str | None = None,
    current_optimizer_step: int | None = None,
) -> tuple[str, ...]:
    resolved_plan = _resolve_plan(release, plan)
    obligations = _validate_ledger(release, ledger, plan=resolved_plan)
    closed = set(closed_obligations(
        release, ledger, plan=resolved_plan,
        current_checkpoint_sha256=current_checkpoint_sha256,
        current_optimizer_step=current_optimizer_step))
    blocked = set(resolved_plan.blocked_capabilities)
    mastered: list[str] = []
    mastered_set: set[str] = set()
    for definition in release_capabilities(release):
        if definition.capability_id in blocked:
            continue
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
    release: FactoryRelease, ledger: EvidenceLedger, receipt: EvidenceReceipt, *,
    plan: AutonomyPlan | None = None,
    current_checkpoint_sha256: str | None = None,
    current_optimizer_step: int | None = None,
) -> EvidenceLedger:
    obligations = _validate_ledger(release, ledger, plan=plan)
    if not isinstance(receipt, EvidenceReceipt):
        raise TypeError("AUTONOMY_INVALID_EVIDENCE_RECEIPT")
    obligation = obligations.get(receipt.obligation_id)
    if obligation is None:
        raise ValueError("AUTONOMY_UNKNOWN_EVIDENCE_OBLIGATION")
    if receipt.passed and receipt.specimen_count < obligation.minimum_specimens:
        raise ValueError("AUTONOMY_INSUFFICIENT_EVIDENCE_SPECIMENS")
    if receipt.evidence_id in {item.evidence_id for item in ledger.receipts}:
        raise ValueError("AUTONOMY_DUPLICATE_EVIDENCE_RECEIPT")
    current = _validate_current_context(
        current_checkpoint_sha256, current_optimizer_step)
    if current is not None and not _receipt_is_current(receipt, current):
        raise ValueError("AUTONOMY_EVIDENCE_CURRENT_CHECKPOINT_MISMATCH")
    return EvidenceLedger(
        ledger.factory_release_sha256, ledger.autonomy_plan_sha256,
        (*ledger.receipts, receipt), ledger.interventions,
        ledger.rejected_attempts)


def record_teaching_intervention(
    release: FactoryRelease, ledger: EvidenceLedger, receipt: TeachingReceipt, *,
    plan: AutonomyPlan | None = None,
    current_checkpoint_sha256: str | None = None,
    current_optimizer_step: int | None = None,
) -> EvidenceLedger:
    obligations = _validate_ledger(release, ledger, plan=plan)
    if not isinstance(receipt, TeachingReceipt):
        raise TypeError("AUTONOMY_INVALID_TEACHING_RECEIPT")
    obligation = obligations.get(receipt.obligation_id)
    if obligation is None:
        raise ValueError("AUTONOMY_UNKNOWN_EVIDENCE_OBLIGATION")
    latest = _latest_receipts(ledger).get(receipt.obligation_id)
    if latest is None or latest.passed:
        raise ValueError("AUTONOMY_TEACHING_REQUIRES_FAILED_EVIDENCE")
    if (receipt.parent_checkpoint_sha256 != latest.checkpoint_sha256 or
            receipt.parent_optimizer_step != latest.optimizer_step):
        raise ValueError("AUTONOMY_TEACHING_PARENT_EVIDENCE_MISMATCH")
    current = _validate_current_context(
        current_checkpoint_sha256, current_optimizer_step)
    if current is not None and (
            receipt.parent_checkpoint_sha256 != current[0] or
            receipt.parent_optimizer_step != current[1]):
        raise ValueError("AUTONOMY_TEACHING_CURRENT_CHECKPOINT_MISMATCH")
    work = _work_item(
        release, obligation,
        evidence_complete_capabilities(release, ledger, plan=plan))
    if receipt.teaching_option_id not in work.teaching_option_ids:
        raise ValueError("AUTONOMY_TEACHING_OPTION_NOT_RELEASED")
    definition = _capability_definitions(release)[obligation.capability_id]
    provider = {item.adapter_id: item for item in release.source_adapters}[definition.source_adapter_id]
    coverage = _coverage_by_capability(release)[obligation.capability_id]
    if (not receipt.selected_provider_id or
            not receipt.provider_implementation_sha256 or
            not receipt.specimen_ids or not receipt.specimen_content_sha256 or
            not receipt.variation_axes or receipt.optimizer_step_delta is None):
        raise ValueError("AUTONOMY_TEACHING_PROVENANCE_UNPROVEN")
    if (receipt.selected_provider_id != provider.adapter_id or
            receipt.provider_implementation_sha256 != provider.implementation_sha256):
        raise ValueError("AUTONOMY_TEACHING_PROVIDER_MISMATCH")
    if receipt.variation_axes != coverage.variation_axes:
        raise ValueError("AUTONOMY_TEACHING_VARIATION_AXES_MISMATCH")
    if receipt.intervention_id in {
            item.intervention_id for item in ledger.interventions}:
        raise ValueError("AUTONOMY_DUPLICATE_TEACHING_RECEIPT")
    return EvidenceLedger(
        ledger.factory_release_sha256, ledger.autonomy_plan_sha256,
        ledger.receipts, (*ledger.interventions, receipt),
        ledger.rejected_attempts)


def record_rejected_teaching_attempt(
    release: FactoryRelease, ledger: EvidenceLedger,
    receipt: RejectedTeachingAttemptReceipt, *,
    plan: AutonomyPlan | None = None,
    current_checkpoint_sha256: str | None = None,
    current_optimizer_step: int | None = None,
) -> EvidenceLedger:
    """Append a truthful no-retained-gain teaching outcome."""
    obligations = _validate_ledger(release, ledger, plan=plan)
    if not isinstance(receipt, RejectedTeachingAttemptReceipt):
        raise TypeError("AUTONOMY_INVALID_REJECTED_TEACHING_ATTEMPT")
    obligation = obligations.get(receipt.obligation_id)
    if obligation is None:
        raise ValueError("AUTONOMY_UNKNOWN_EVIDENCE_OBLIGATION")
    latest = _latest_receipts(ledger).get(receipt.obligation_id)
    if (latest is None or latest.passed or
            receipt.parent_evidence_id != latest.evidence_id or
            receipt.retained_checkpoint_sha256 != latest.checkpoint_sha256 or
            receipt.retained_optimizer_step != latest.optimizer_step):
        raise ValueError("AUTONOMY_REJECTED_ATTEMPT_PARENT_EVIDENCE_MISMATCH")
    current = _validate_current_context(
        current_checkpoint_sha256, current_optimizer_step)
    if current is not None and (
            receipt.retained_checkpoint_sha256 != current[0] or
            receipt.retained_optimizer_step != current[1]):
        raise ValueError("AUTONOMY_REJECTED_ATTEMPT_CURRENT_CHECKPOINT_MISMATCH")
    work = _work_item(
        release, obligation,
        evidence_complete_capabilities(release, ledger, plan=plan))
    if receipt.teaching_option_id not in work.teaching_option_ids:
        raise ValueError("AUTONOMY_REJECTED_ATTEMPT_OPTION_NOT_RELEASED")
    definition = _capability_definitions(release)[obligation.capability_id]
    provider = {
        item.adapter_id: item for item in release.source_adapters
    }[definition.source_adapter_id]
    if (receipt.selected_provider_id != provider.adapter_id or
            receipt.provider_implementation_sha256 !=
            provider.implementation_sha256):
        raise ValueError("AUTONOMY_REJECTED_ATTEMPT_PROVIDER_MISMATCH")
    if receipt.attempt_id in {
            item.attempt_id for item in ledger.rejected_attempts}:
        return ledger
    return EvidenceLedger(
        ledger.factory_release_sha256, ledger.autonomy_plan_sha256,
        ledger.receipts, ledger.interventions,
        (*ledger.rejected_attempts, receipt))


def _work_item(
    release: FactoryRelease, obligation: EvidenceObligation,
    mastered: tuple[str, ...],
) -> CurriculumWorkItem:
    definition = _capability_definitions(release)[obligation.capability_id]
    options = (tuple(item.option_id for item in release.teaching_options
                     if item.capability_id == obligation.capability_id)
               if isinstance(release, FactoryRelease) else
               release.execution_plan.capability_map[obligation.capability_id].teaching_option_ids)
    return CurriculumWorkItem(
        capability_id=obligation.capability_id,
        obligation=obligation,
        teaching_option_ids=options,
        evidence_complete_prerequisites=tuple(
            item for item in mastered if item in definition.prerequisites),
    )


def _failed_remediation_cycles(
    ledger: EvidenceLedger, obligation_id: str,
) -> int:
    """Count retained interventions that still failed fresh child evidence.

    A later pass resets the bounded-remediation budget. Rejected challengers
    never appear in the intervention ledger and therefore cannot consume it.
    """
    relevant_receipts = tuple(
        item for item in ledger.receipts
        if item.obligation_id == obligation_id)
    last_pass_index = max(
        (index for index, item in enumerate(relevant_receipts)
         if item.passed), default=-1)
    failed_receipts = tuple(
        item for index, item in enumerate(relevant_receipts)
        if index > last_pass_index and not item.passed)
    failed_evidence_ids = {item.evidence_id for item in failed_receipts}
    failed_children = {
        (item.checkpoint_sha256, item.optimizer_step)
        for item in failed_receipts
    }
    retained_failures = sum(
        1 for item in ledger.interventions
        if (item.obligation_id == obligation_id and
            (item.checkpoint_sha256, item.optimizer_step) in failed_children))
    rejected = sum(
        1 for item in ledger.rejected_attempts
        if (item.obligation_id == obligation_id and
            item.parent_evidence_id in failed_evidence_ids))
    return retained_failures + rejected


def _next_work_decision(
    release: FactoryRelease, ledger: EvidenceLedger, *,
    plan: AutonomyPlan | None = None,
    current_checkpoint_sha256: str | None = None,
    current_optimizer_step: int | None = None,
) -> tuple[CurriculumWorkItem | None, tuple[str, ...]]:
    """Choose useful work while bounding repeated remediation monopolies."""
    _validate_ledger(release, ledger, plan=plan)
    resolved_plan = _resolve_plan(release, plan)
    latest = _latest_receipts(ledger)
    closed = set(closed_obligations(
        release, ledger, plan=resolved_plan,
        current_checkpoint_sha256=current_checkpoint_sha256,
        current_optimizer_step=current_optimizer_step))
    mastered = evidence_complete_capabilities(
        release, ledger, plan=resolved_plan,
        current_checkpoint_sha256=current_checkpoint_sha256,
        current_optimizer_step=current_optimizer_step)
    mastered_set = set(mastered)
    definitions = _capability_definitions(release)
    blocked = set(resolved_plan.blocked_capabilities)

    def eligible(obligation: EvidenceObligation) -> bool:
        definition = definitions[obligation.capability_id]
        return (obligation.obligation_id not in closed and
                obligation.capability_id not in blocked and
                set(definition.prerequisites) <= mastered_set and
                set(obligation.requires_capabilities) <= mastered_set)

    ordered_open: list[EvidenceObligation] = []
    for definition in release_capabilities(release):
        if definition.capability_id in mastered_set:
            continue
        if definition.capability_id in blocked:
            continue
        if not set(definition.prerequisites) <= mastered_set:
            continue
        ordered_open.extend(
            obligation for obligation in obligations_for_capability(
                release, definition.capability_id, plan=resolved_plan)
            if eligible(obligation)
        )
    if not ordered_open:
        return None, ()

    deferred = tuple(
        obligation.obligation_id
        for obligation in ordered_open
        if _failed_remediation_cycles(
            ledger, obligation.obligation_id) >=
            resolved_plan.remediation_failure_limit
    )
    deferred_set = set(deferred)
    selectable = tuple(
        item for item in ordered_open
        if item.obligation_id not in deferred_set)
    if not selectable:
        return None, deferred
    selectable_ids = {item.obligation_id for item in selectable}

    # Failed work still outranks new breadth until it reaches the bounded
    # remediation limit above.
    for receipt in reversed(ledger.receipts):
        if receipt.passed or receipt.obligation_id not in selectable_ids:
            continue
        obligation = next(
            item for item in selectable
            if item.obligation_id == receipt.obligation_id)
        if latest[receipt.obligation_id] == receipt:
            return _work_item(release, obligation, mastered), deferred

    return _work_item(release, selectable[0], mastered), deferred


def next_work(
    release: FactoryRelease, ledger: EvidenceLedger, *, plan: AutonomyPlan | None = None,
    current_checkpoint_sha256: str | None = None,
    current_optimizer_step: int | None = None,
) -> CurriculumWorkItem | None:
    """Return the next legal semantic proof target, never a training command."""
    return _next_work_decision(
        release, ledger, plan=plan,
        current_checkpoint_sha256=current_checkpoint_sha256,
        current_optimizer_step=current_optimizer_step)[0]

class AutonomyActionKind(str, Enum):
    SOURCE_COVERAGE = "SOURCE_COVERAGE"
    TEACHING = "TEACHING"
    LEARNING_EVIDENCE = "LEARNING_EVIDENCE"
    SAFE_HOLD = "SAFE_HOLD"
    QUALIFICATION = "QUALIFICATION"


@dataclass(frozen=True)
class AutonomyAction:
    kind: AutonomyActionKind
    source_coverage_debt: str | None = None
    evidence_work: CurriculumWorkItem | None = None
    teaching_work: TeachingWorkItem | None = None
    deferred_obligation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AutonomyActionKind):
            raise ValueError("AUTONOMY_ACTION_KIND_INVALID")
        if (len(set(self.deferred_obligation_ids)) !=
                len(self.deferred_obligation_ids) or
                any(not isinstance(item, str) or not item
                    for item in self.deferred_obligation_ids)):
            raise ValueError("AUTONOMY_ACTION_DEFERRAL_INVALID")
        if self.kind is AutonomyActionKind.SOURCE_COVERAGE:
            if (not self.source_coverage_debt or self.evidence_work is not None or
                    self.teaching_work is not None or
                    self.deferred_obligation_ids):
                raise ValueError("AUTONOMY_SOURCE_ACTION_INVALID")
        elif self.kind is AutonomyActionKind.TEACHING:
            if (self.source_coverage_debt is not None or self.evidence_work is not None or
                    self.teaching_work is None):
                raise ValueError("AUTONOMY_TEACHING_ACTION_INVALID")
        elif self.kind is AutonomyActionKind.LEARNING_EVIDENCE:
            if (self.source_coverage_debt is not None or self.evidence_work is None or
                    self.teaching_work is not None):
                raise ValueError("AUTONOMY_LEARNING_ACTION_INVALID")
        elif self.kind is AutonomyActionKind.SAFE_HOLD:
            if (self.source_coverage_debt is not None or
                    self.evidence_work is not None or
                    self.teaching_work is not None or
                    not self.deferred_obligation_ids):
                raise ValueError("AUTONOMY_SAFE_HOLD_ACTION_INVALID")
        elif (self.source_coverage_debt is not None or self.evidence_work is not None or
              self.teaching_work is not None or self.deferred_obligation_ids):
            raise ValueError("AUTONOMY_QUALIFICATION_ACTION_INVALID")


def next_action(
    release: FactoryRelease, ledger: EvidenceLedger, *, plan: AutonomyPlan | None = None,
    current_checkpoint_sha256: str | None = None,
    current_optimizer_step: int | None = None,
) -> AutonomyAction:
    """Route one autonomous iteration without performing the selected work."""
    _validate_ledger(release, ledger, plan=plan)
    resolved_plan = _resolve_plan(release, plan)
    debt = next_source_coverage_debt(resolved_plan)
    if debt is not None:
        return AutonomyAction(AutonomyActionKind.SOURCE_COVERAGE,
                              source_coverage_debt=debt)
    work, deferred = _next_work_decision(
        release, ledger, plan=resolved_plan,
        current_checkpoint_sha256=current_checkpoint_sha256,
        current_optimizer_step=current_optimizer_step)
    if work is None and deferred:
        return AutonomyAction(
            AutonomyActionKind.SAFE_HOLD,
            deferred_obligation_ids=deferred)
    if work is not None:
        latest_failed = _latest_receipts(ledger).get(work.obligation.obligation_id)
        current = _validate_current_context(
            current_checkpoint_sha256, current_optimizer_step)
        if (latest_failed is not None and not latest_failed.passed and
                _receipt_is_current(latest_failed, current)):
            latest_intervention = _latest_interventions(ledger).get(
                work.obligation.obligation_id)
            if (latest_intervention is None or
                    latest_intervention.parent_checkpoint_sha256 !=
                    latest_failed.checkpoint_sha256 or
                    latest_intervention.parent_optimizer_step !=
                    latest_failed.optimizer_step):
                return AutonomyAction(
                    AutonomyActionKind.TEACHING,
                    teaching_work=TeachingWorkItem(
                        work.capability_id, work.obligation,
                        work.teaching_option_ids, latest_failed),
                    deferred_obligation_ids=deferred)
        return AutonomyAction(AutonomyActionKind.LEARNING_EVIDENCE,
                              evidence_work=work,
                              deferred_obligation_ids=deferred)
    return AutonomyAction(AutonomyActionKind.QUALIFICATION)


def rebind_evidence_ledger(
    release: FactoryRelease, ledger: EvidenceLedger, *,
    old_plan: AutonomyPlan, new_plan: AutonomyPlan,
) -> EvidenceLedger:
    """Carry forward only receipts whose semantic obligation is unchanged."""
    _validate_ledger(release, ledger, plan=old_plan)
    if (old_plan.factory_release_sha256 != release.release_sha256 or
            new_plan.factory_release_sha256 != release.release_sha256):
        raise ValueError("AUTONOMY_PLAN_RELEASE_MISMATCH")
    old_obligations = _obligation_map(release, old_plan)
    new_obligations = _obligation_map(release, new_plan)
    for receipt in ledger.receipts:
        old = old_obligations.get(receipt.obligation_id)
        new = new_obligations.get(receipt.obligation_id)
        if old is None or new is None or old != new:
            raise ValueError(
                "AUTONOMY_PLAN_REBIND_INVALIDATES_EVIDENCE:" + receipt.obligation_id)
    for attempt in ledger.rejected_attempts:
        old = old_obligations.get(attempt.obligation_id)
        new = new_obligations.get(attempt.obligation_id)
        if old is None or new is None or old != new:
            raise ValueError(
                "AUTONOMY_PLAN_REBIND_INVALIDATES_ATTEMPT:" +
                attempt.obligation_id)
    rebound = EvidenceLedger(
        release.release_sha256, new_plan.digest(),
        ledger.receipts, ledger.interventions, ledger.rejected_attempts)
    _validate_ledger(release, rebound, plan=new_plan)
    return rebound


def reconcile_successor_evidence(
    previous_release, current_release, ledger: EvidenceLedger, *,
    previous_plan: AutonomyPlan, current_plan: AutonomyPlan,
) -> EvidenceLedger:
    """Carry only unchanged semantic/source/answer/coverage evidence forward.

    Release identity is not evidence identity.  A successor may retain learner
    receipts for a capability only when its semantic declaration and the
    source, answer-schema, and coverage projections are byte-identical and the
    concrete learner obligation itself is unchanged.  Teaching interventions
    remain in the immutable predecessor snapshot; they are not re-authorized
    across a release boundary.
    """
    from .executable_release import ExecutableFactoryRelease

    if (not isinstance(previous_release, ExecutableFactoryRelease) or
            not isinstance(current_release, ExecutableFactoryRelease)):
        raise TypeError("AUTONOMY_SUCCESSOR_RECONCILIATION_REQUIRES_V2")
    previous_release.verify()
    current_release.verify_successor_of(previous_release)
    _validate_ledger(previous_release, ledger, plan=previous_plan)
    if current_plan.factory_release_sha256 != current_release.release_sha256:
        raise ValueError("AUTONOMY_PLAN_RELEASE_MISMATCH")

    old_semantics = previous_release.curriculum.capability_map
    new_semantics = current_release.curriculum.capability_map
    old_projection = {
        item.capability_id: item
        for item in previous_release.execution_plan.capability_projection_digests
    }
    new_projection = {
        item.capability_id: item
        for item in current_release.execution_plan.capability_projection_digests
    }
    unchanged_capabilities = {
        capability_id
        for capability_id in set(old_semantics) & set(new_semantics)
        if old_semantics[capability_id] == new_semantics[capability_id]
        and all(
            getattr(old_projection[capability_id], field)
            == getattr(new_projection[capability_id], field)
            for field in ("source", "answer_schema", "coverage")
        )
    }
    old_obligations = _obligation_map(previous_release, previous_plan)
    new_obligations = _obligation_map(current_release, current_plan)
    carried = tuple(
        receipt for receipt in ledger.receipts
        if (receipt.obligation_id in old_obligations
            and receipt.obligation_id in new_obligations
            and old_obligations[receipt.obligation_id]
            == new_obligations[receipt.obligation_id]
            and old_obligations[receipt.obligation_id].capability_id
            in unchanged_capabilities)
    )
    reconciled = EvidenceLedger(
        current_release.release_sha256, current_plan.digest(), carried, ())
    _validate_ledger(current_release, reconciled, plan=current_plan)
    return reconciled
