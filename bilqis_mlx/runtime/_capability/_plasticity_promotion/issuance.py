from __future__ import annotations

from pathlib import Path

from .common import invalid
from .evidence import (
    _foundation_capabilities,
    _school_for_receipt,
    evidence_digest,
    evidence_interval,
    validate_sweep_evidence,
)
from .receipt import (
    RECEIPT_SCHEMA,
)


def validated_promotion_transition_fields(run_dir: Path, retained_state, decision):
    """Validate current immutable runtime custody and return exact receipt fields."""
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.learning.atlas_candidate import CandidateState
    from bilqis_mlx.learning.atlas_retention_decision import (
        CandidateRetentionDecision, _require_issued_decision,
    )
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
        bind_accepted_execution_cache, load_accepted_generation,
    )
    from bilqis_mlx.state_dag import read_current

    run_dir = Path(run_dir).resolve()
    if (type(retained_state) is not CandidateState
            or type(decision) is not CandidateRetentionDecision):
        invalid()
    _require_issued_decision(decision)
    decision.__post_init__()
    if not decision.accepted:
        invalid()
    parent = load_accepted_generation(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    if cache.run_id != parent.run_id or cache.generation != parent.generation:
        invalid()
    parent_identity = candidate_identity_digest(parent.retained_state)
    candidate_identity = candidate_identity_digest(retained_state)
    if (decision.parent_generation != parent_identity
            or decision.candidate_generation != candidate_identity
            or retained_state.optimizer_step <= parent.retained_state.optimizer_step):
        invalid()

    current = read_current(run_dir)
    if current.get("run_id") != parent.run_id or type(current.get("generation")) is not int:
        invalid()
    current_school = _school_for_receipt(run_dir, current)
    if (current_school.current_student.sha256 != candidate_identity
            or current_school.current_student.optimizer_step != retained_state.optimizer_step):
        invalid()
    initial_release = parent.run_identity.factory_release_sha256
    foundation = _foundation_capabilities(run_dir, initial_release)
    if (current_school.promotion_sweep_attempt_student_sha256 != candidate_identity
            or tuple(current_school.promotion_sweep_attempt_scope) != foundation):
        invalid()
    evidence = evidence_interval(
        run_dir,
        current_generation=current["generation"],
        candidate_sha256=candidate_identity,
        optimizer_step=retained_state.optimizer_step,
        foundation=foundation,
    )
    outcome, debt = validate_sweep_evidence(evidence, foundation)
    final_school = evidence[-1][2]
    return (
        ("run_id", parent.run_id),
        ("parent_generation", parent.generation),
        ("candidate_generation", parent.generation + 1),
        ("parent_manifest_sha256", cache.accepted_manifest_sha256),
        ("parent_candidate_identity_sha256", parent_identity),
        ("candidate_identity_sha256", candidate_identity),
        ("optimizer_step", retained_state.optimizer_step),
        ("decision_sha256", decision.digest),
        ("initial_factory_release_sha256", initial_release),
        ("foundation_capability_ids", foundation),
        ("promotion_state_generations", tuple(item[0] for item in evidence)),
        ("promotion_evidence_sha256", evidence_digest(evidence)),
        ("assessment_epoch", final_school.grade_exam_epoch),
        ("outcome", outcome),
        ("carried_debt", debt),
        ("schema_version", RECEIPT_SCHEMA),
    )


def promotion_transition_pending(run_dir: Path, retained_state) -> bool:
    """Report a real retained-candidate promotion attempt, never a grade label."""
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.learning.atlas_candidate import CandidateState
    from bilqis_mlx.learning.atlas_plasticity import FOUNDATION_MODE
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
        bind_accepted_execution_cache, load_accepted_generation,
    )
    from bilqis_mlx.state_dag import read_current

    run_dir = Path(run_dir).resolve()
    if type(retained_state) is not CandidateState:
        invalid()
    if retained_state.policy.mode != FOUNDATION_MODE:
        return False
    parent = load_accepted_generation(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    if cache.run_id != parent.run_id or cache.generation != parent.generation:
        invalid()
    if retained_state.optimizer_step <= parent.retained_state.optimizer_step:
        return False
    current = read_current(run_dir)
    if current.get("run_id") != parent.run_id or type(current.get("generation")) is not int:
        invalid()
    school = _school_for_receipt(run_dir, current)
    attempt_student = school.promotion_sweep_attempt_student_sha256
    attempt_scope = tuple(school.promotion_sweep_attempt_scope)
    if attempt_student is None and not attempt_scope:
        return False
    candidate_identity = candidate_identity_digest(retained_state)
    foundation = _foundation_capabilities(
        run_dir, parent.run_identity.factory_release_sha256)
    return (
        school.current_student.sha256 == candidate_identity
        and school.current_student.optimizer_step == retained_state.optimizer_step
        and attempt_student == candidate_identity
        and attempt_scope == foundation
    )
