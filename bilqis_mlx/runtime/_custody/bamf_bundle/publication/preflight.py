"""Publish and replay parent-only C05 skip evidence without candidate custody."""
from pathlib import Path

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.learning.teacher_visit_identity import (
    TeacherVisitIdentity, require_teacher_visit_receipt,
)
from bilqis_mlx.runtime.baseline.lifecycle import (
    BaselineComparisonIdentity, BaselineLedger, BaselineLifecycleState,
)
from bilqis_mlx.runtime.retention.local_preflight import require_preflight
from bilqis_mlx.runtime.capability_evaluation import _answer_identity
from bilqis_mlx.semantics.domains import contract_digest

from ..records import canonical, invalid, sha
from .storage import _live_bundle_manifest, _pointer_lock, _read_pointer

PERFECT_TARGET_SKIPPED = "PERFECT_TARGET_SKIPPED"
PREFLIGHT_EXHAUSTED = "PREFLIGHT_EXHAUSTED"
EVENT = "BAMF_PERFECT_TARGET_SKIPPED"
SCHEMA = "bilqis.bamf.c05-perfect-target-skip/v1"


def _evidence(preflight):
    assessment = preflight.assessment
    correct, total = assessment.score(preflight.visit.capability_id)
    return {
        "schema": SCHEMA,
        "teacher_visit": preflight.visit.to_record(),
        "capability": preflight.visit.capability_id,
        "cadence": preflight.cadence,
        "comparison": preflight.comparison.to_record(),
        "source_seed": preflight.seed,
        "journal_ordinal": preflight.journal_ordinal,
        "plan_sha256": preflight.plan_sha256,
        "case_census_sha256": assessment.cohort.expected_case_digest,
        "assessment_sha256": assessment.digest(),
        "parent_correct": correct,
        "total": total,
        "cases": [
            {"id": case.case_id,
             "gold_sha256": contract_digest(_answer_identity(case.gold)),
             "answer_sha256": contract_digest(_answer_identity(result.answer)),
             "result": result.replay_record()}
            for case, result in zip(assessment.cohort.cases, assessment.results)
        ],
    }


def _check_evidence(evidence, parent, manifest):
    if not isinstance(evidence, dict):
        invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    from bilqis_mlx.learning._atlas_candidate.identity_binding import (
        candidate_identity_for_canonical_consumer,
    )
    identity = TeacherVisitIdentity.from_record(evidence.get("teacher_visit"))
    comparison = BaselineComparisonIdentity.from_record(evidence.get("comparison"))
    capability = evidence.get("capability")
    cadence = evidence.get("cadence")
    cases = evidence.get("cases")
    total = evidence.get("total")
    if (evidence.get("schema") != SCHEMA
            or identity.capability_id != capability
            or identity.run_identity_sha256 != parent.run_identity.digest
            or identity.run_seed != parent.run_identity.run_seed
            or identity.selection_seed != parent.teacher_state.get("next_seed")
            or identity.cursor != parent.teacher_state.get("cursor")
            or identity.generation != parent.generation
            or identity.accepted_manifest_sha256 != manifest
            or identity.student_sha256 != candidate_identity_for_canonical_consumer(
                parent.retained_state)
            or comparison.capability_id != capability
            or comparison.correction_frontier_sha256 != contract_digest(parent.correction_frontier)
            or comparison.evaluation_contract_sha256 != contract_digest(parent.evaluation_contract)
            or BaselineLedger.from_optional_record(parent.baseline_evidence).state_for(
                comparison) is BaselineLifecycleState.UNMEASURED
            or not isinstance(cadence, dict)
            or cadence.get("run_id") != parent.run_id
            or capability not in cadence.get("authorized_capability_ids", ())
            or type(total) is not int or total <= 0
            or evidence.get("parent_correct") != total
            or not isinstance(cases, list) or len(cases) != total
            or any(not isinstance(item, dict) or not isinstance(item.get("id"), str)
                   or not isinstance(item.get("answer_sha256"), str)
                   or not isinstance(item.get("gold_sha256"), str) for item in cases)
            or len({item["id"] for item in cases}) != total
            or any(item["answer_sha256"] != item["gold_sha256"]
                   for item in cases)):
        invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    require_teacher_visit_receipt(identity)


def record_perfect_target_skip(run_dir, parent, preflight):
    """Write the neutral event under the same pointer lock as B13 rejections."""
    from bilqis_mlx.runtime import checkpoint_outbox, checkpoints
    from bilqis_mlx.runtime.active_grade_cadence_custody import read_current_cadence
    require_preflight(preflight)
    if not preflight.skip:
        invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    root = Path(run_dir)
    with _pointer_lock(root):
        pointer = _read_pointer(root / "bamf-state.json")
        if (pointer is None or pointer["run_id"] != parent.run_id
                or pointer["generation"] != parent.generation
                or pointer["manifest_sha256"] != preflight.visit.accepted_manifest_sha256):
            invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
        manifest = _live_bundle_manifest(root, pointer)
        step = parent.retained_state.optimizer_step
        if manifest.get("optimizer", {}).get("step") != step:
            invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
        evidence = _evidence(preflight)
        _check_evidence(evidence, parent, pointer["manifest_sha256"])
        authority = {
            "run_id": parent.run_id, "generation": parent.generation,
            "student_manifest_sha256": pointer["manifest_sha256"],
            "optimizer_step": step, "evidence": evidence,
        }
        raw = canonical(authority)
        digest = sha(raw)
        data_plane().put_object(digest, raw)
        event = {"event": EVENT, **authority, "preflight_authority_sha256": digest}
        lineage = {"run_id": parent.run_id, "generation": parent.generation}
        outbox = checkpoint_outbox.with_delivery_outbox(lineage, (event,))["delivery_outbox"]
        state = read_current_cadence(root)
        if state is None or state.cadence_sha256 != preflight.cadence["cadence_sha256"]:
            if checkpoints._reconcile_delivery_outbox(
                    root, {**lineage, "delivery_outbox": outbox}, publish_missing=False):
                return digest
            invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
        checkpoints._reconcile_delivery_outbox(root, {**lineage, "delivery_outbox": outbox})
        return digest


def authenticate_perfect_target_skip(event, parent, manifest):
    from bilqis_mlx.runtime import checkpoint_outbox
    if event.get("event") != EVENT:
        invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    authority = {key: event.get(key) for key in (
        "run_id", "generation", "student_manifest_sha256", "optimizer_step", "evidence")}
    raw = canonical(authority)
    digest = sha(raw)
    if (authority["run_id"] != parent.run_id
            or authority["generation"] != parent.generation
            or authority["student_manifest_sha256"] != manifest
            or authority["optimizer_step"] != parent.retained_state.optimizer_step
            or event.get("preflight_authority_sha256") != digest
            or data_plane().get_object(digest) != raw
            or not checkpoint_outbox.ordinary_outbox_lineage(
                {"run_id": parent.run_id, "generation": parent.generation}, [event])):
        invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    _check_evidence(authority["evidence"], parent, manifest)
    return authority["evidence"]


def skip_only_exhaustion(run_dir, parent, release, cadence):
    """Recognize exhausted neutral work for this unchanged accepted scope."""
    from bilqis_mlx.runtime.retention.protection_plan_compiler import _rubric_sha256
    from bilqis_mlx.runtime.priority_rejection_replay import authenticated_rejection_event
    if not (Path(run_dir) / "bamf-state.json").is_file():
        return False
    manifest = parent.retained_state.custody.manifest_sha256
    events = data_plane().indexed_event_tail(
        run_dir, terminal_generation=parent.generation)["events"]
    keys = ("run_id", "cadence_epoch", "active_grade_activation_sha256",
            "active_grade_definition_sha256", "member_census_sha256", "policy_epoch")
    skipped = False
    for event in events:
        evidence = event.get("evidence") or {}
        recorded = evidence.get("cadence") or {}
        if any(recorded.get(key) != cadence.get(key) for key in keys):
            continue
        if event.get("event") == "BAMF_CANDIDATE_REJECTED":
            if authenticated_rejection_event(event, parent, manifest):
                return False
            continue
        evidence = authenticate_perfect_target_skip(event, parent, manifest)
        comparison = evidence["comparison"]
        if (comparison["factory_release_sha256"] == release.release_sha256
                and comparison["source_sha256"] == release.execution_plan.projection_digests.source
                and comparison["rubric_sha256"] == _rubric_sha256(release)):
            skipped = True
    return skipped
