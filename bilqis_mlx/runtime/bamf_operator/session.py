"""C16.3 persistent BAMF-native human session.

This coordinator composes existing owners.  It is not a curriculum, teacher,
retention, source, optimizer, or publication authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import time

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.atlas_retention_decision import (
    issue_factory_retention_decision,
)
from bilqis_mlx.learning.student_ops import train_bamf_factory_step
from bilqis_mlx.paths import LEGACY_SOURCE
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_visit_provenance import BamfVisitProvenance
from bilqis_mlx.runtime.bamf_bundle import (
    authenticate_bamf_execution_feature_context,
    read_accepted_generation_feature_context, record_bamf_rejection,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, load_accepted_generation,
)
from bilqis_mlx.runtime.factory_candidate_training import FactoryDeliveryObservation
from bilqis_mlx.runtime.factory_retention_owner import (
    evaluate_factory_retention_candidate, measure_factory_foundation_progress,
)
from bilqis_mlx.runtime.foundation_teacher_owner import (
    derive_accepted_teacher_successor, select_foundation_teacher_visit,
)
from bilqis_mlx.semantics.atlas.feature_io import persist_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactIdentity, resolve_atlas_artifact_selection,
)
from .locking import bamf_operator_lock


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_FIRST_STUDENT.INVALID, reason=reason)


@dataclass(frozen=True)
class BamfOperatorResult:
    status: str
    visits: int
    accepted: int
    rejected: int
    generation: int
    optimizer_step: int


class _Capture:
    """Minimal durable delivery evidence required by the C02 bridge."""

    def __init__(self, run_dir: Path, visit_id: str, option_id: str):
        from bilqis_mlx.runtime.teacher_observation_capture import store_sidecar
        self.run_dir = run_dir
        self.attempt_id = sha256(
            f"bamf-c16.3:{visit_id}".encode()).hexdigest()
        self.selected_option = option_id
        self.proposal_id = store_sidecar(run_dir, {
            "schema": "bilqis.bamf.c16.3-operator-proposal/v1",
            "attempt_id": self.attempt_id,
            "visit_id": visit_id,
            "selected_option": option_id,
        })["sha256"]

    def delivery(self, _release, capability, step, rows, **evidence):
        from bilqis_mlx.runtime.teacher_observation_capture import store_sidecar
        store_sidecar(self.run_dir, {
            "schema": "bilqis.bamf.c16.3-operator-delivery/v1",
            "attempt_id": self.attempt_id,
            "proposal_id": self.proposal_id,
            "capability": capability,
            "step": step,
            "row_ids": [row["id"] for row in rows],
            "seed": evidence.get("seed"),
        })


def _seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(sha256(payload).digest()[:8], "big")


def _accepted_lease_digest(run_dir: Path, host: AcceptedRuntimeHost):
    from bilqis_mlx.runtime.atlas_lease_storage import classify_accepted_atlas_epoch
    epoch = classify_accepted_atlas_epoch(run_dir)
    if epoch == "staged":
        return "staged"
    source_authority = host.source_authority()
    if epoch == "v2":
        from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_lease_v2
        lease = read_accepted_atlas_lease_v2(
            run_dir, source_authority=source_authority)
    else:
        from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_lease
        lease = read_accepted_atlas_lease(
            run_dir, source_authority=source_authority)
    if lease is None:
        _invalid("BAMF_OPERATOR_ACCEPTED_ATLAS_LEASE_MISSING")
    return lease.digest()


def _execution_context(run_dir: Path, graph):
    parent = load_accepted_generation(run_dir)
    host = AcceptedRuntimeHost(run_dir)
    context = host.source_context(graph=graph, source_root=LEGACY_SOURCE.resolve())
    _accepted_lease_digest(run_dir, host)
    accepted = read_accepted_generation_feature_context(run_dir / "bamf-state.json")
    identity = accepted.receipt
    selection = resolve_atlas_artifact_selection(AtlasArtifactIdentity(
        identity.source_atlas_bundle_id,
        identity.source_release_sha256,
        identity.source_source_bundle_id,
    ))
    authenticated = authenticate_bamf_execution_feature_context(
        parent, selection.path, run_dir)
    predecessor = accepted.construction_predecessor
    feature = persist_feature_manifest(
        authenticated.features, run_dir / "operator-artifacts" / "features",
        predecessor=predecessor)
    return parent, context, selection.path, feature.path


def _next_target(context, parent, atlas_path: str, run_dir: Path):
    assessment = measure_factory_foundation_progress(
        context, atlas_path, run_dir=run_dir)
    execution = context.release.execution_plan.capabilities
    mastered = {
        item.capability_id for item in execution
        if assessment.score(item.capability_id)[0]
        == assessment.score(item.capability_id)[1]
    }
    for item in execution:
        if item.capability_id in mastered:
            continue
        if set(item.prerequisites) <= mastered:
            return item, assessment
    if len(mastered) == len(execution):
        return None, assessment
    _invalid("BAMF_OPERATOR_PREREQUISITE_DEADLOCK")


def _visit(run_dir: Path, graph, reserve_gib: float):
    parent, context, atlas_path, feature_path = _execution_context(run_dir, graph)
    target, _assessment = _next_target(context, parent, atlas_path, run_dir)
    if target is None:
        return "COMPLETE"
    school = SimpleNamespace(
        stage="MAIN",
        current_student=SimpleNamespace(
            sha256=candidate_identity_digest(parent.retained_state)))
    visit, policy, _metadata = select_foundation_teacher_visit(
        run_dir, school, None, "factory/foundation", {},
        capability_id=target.capability_id, lesson_grade=target.grade_id,
        total_capabilities=len(context.release.execution_plan.capabilities))
    source_seed = _seed("c16.3-source-v1", visit.identity.visit_id)
    rows = tuple(context.draw_rows(
        seed=source_seed, capability=target.capability_id, each=1))
    option_id = target.teaching_option_ids[0]
    delivery = describe_delivered_teaching(
        context.release, target.capability_id, option_id, rows)
    capture = _Capture(run_dir, visit.identity.visit_id, option_id)
    observation = FactoryDeliveryObservation(
        capture, parent.retained_state.optimizer_step + 1, rows, source_seed)
    lr = policy.get("lr") if isinstance(policy, dict) else None
    if type(lr) not in (int, float) or lr <= 0:
        _invalid("BAMF_OPERATOR_TEACHER_RATE_INVALID")
    teacher_hp = replace(
        parent.optimizer_hyperparameters, learning_rate=float(lr))
    step = train_bamf_factory_step(
        run_dir, context, parent, atlas_path, feature_path, rows,
        capability=target.capability_id, delivery=delivery,
        requested_count=len(rows), source_seed=source_seed, source_each=1,
        optimizer_step_seed=_seed("c16.3-step-v1", visit.identity.visit_id),
        visit_provenance=BamfVisitProvenance.from_c03_record(
            visit.identity.to_record()),
        teacher_strategy=policy, teacher_hparams=teacher_hp, max_norm=1.0,
        observation=observation)
    evaluation = evaluate_factory_retention_candidate(
        context, step.transaction, atlas_path, target.capability_id,
        run_dir=run_dir)
    decision = issue_factory_retention_decision(evaluation)
    retained = resolve_candidate(step.transaction, accepted=decision.accepted)
    if not decision.accepted:
        record_bamf_rejection(run_dir, parent, {
            "schema": "bilqis.bamf.c16.3-rejection/v1",
            "visit_id": visit.identity.visit_id,
            "capability": target.capability_id,
            "decision": decision.to_record(),
        })
        return "REJECTED"
    successor = derive_accepted_teacher_successor(
        run_dir, retained, visit, delivery_events=({
            "event": "BAMF_C16_3_ACCEPTED",
            "optimizer_step": retained.optimizer_step,
            "capability": target.capability_id,
        },))
    accept_and_publish(
        run_dir, successor, retained, decision=decision,
        feature_sha256=successor.extents.factor_map_digest,
        reserve_gib=reserve_gib,
        training_authorities=step.transaction.training_authorities)
    return "ACCEPTED"


def operate_bamf(
    run_dir: Path, graph, *, minutes: int = 90,
    max_visits: int = 0, reserve_gib: float = 100.0,
) -> BamfOperatorResult:
    """Run the human-authorized BAMF lineage until a bounded stop condition."""
    if (type(minutes) is not int or minutes < 1 or type(max_visits) is not int
            or max_visits < 0 or reserve_gib < 0):
        _invalid("BAMF_OPERATOR_SESSION_BOUNDS_INVALID")
    run_dir = Path(run_dir).resolve()
    deadline = time.monotonic() + minutes * 60
    visits = accepted = rejected = 0
    status = "TIME_LIMIT"
    with bamf_operator_lock(run_dir):
        while time.monotonic() < deadline and (not max_visits or visits < max_visits):
            outcome = _visit(run_dir, graph, reserve_gib)
            if outcome == "COMPLETE":
                status = "FOUNDATION_COMPLETE"
                break
            visits += 1
            if outcome == "REJECTED":
                rejected += 1
                status = "REJECTED_HOLD"
                break
            accepted += 1
        else:
            status = "VISIT_LIMIT" if max_visits and visits >= max_visits else "TIME_LIMIT"
    current = load_accepted_generation(run_dir)
    return BamfOperatorResult(
        status, visits, accepted, rejected, current.generation,
        current.retained_state.optimizer_step)
