"""Restart-safe production assembly for the accepted C07 admission flywheel."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..factory import candidate_realizations
from ..factory.atlas_frontier import (
    AtlasCoverageEpoch,
    AtlasLearnerEvidence,
    PlannerBudget,
)
from ..factory.atlas_frontier_closure import resolve_frontier_closure
from ..factory.atlas_runtime_snapshot import build_accepted_executable_snapshot
from ..factory.live_answers import live_answer_registry
from ..factory.skos_curriculum import (
    LearnedFrontier,
    SOURCE_FAMILY_ADAPTERS,
    compile_semantic_curriculum,
    issue_source_context_transition_authority,
)
from ..errors import ErrorBus, SCHOOL
from ..paths import LEGACY_SOURCE
from ..semantics.atlas import snapshot as atlas_snapshot
from ..source_adapters.school import live_source_registry
from .accepted_corrections import AcceptedRuntimeHost
from .atlas_admission import (
    _accepted_run_lease_identity,
    _accepted_source_registry,
    read_accepted_atlas_factory_release,
    read_accepted_atlas_lease_v2,
    read_accepted_atlas_obligation_credit,
)
from .atlas_admission_policy import AtlasAdmissionContext
from .atlas_admission_policy_v2 import (
    AtlasAdmissionContextV2,
    AtlasDeltaEnvelopeV2,
)
from .atlas_adoption_v2 import (
    adopt_capability_only_atlas_successor_v2,
    adopt_parameter_extension_atlas_successor_v2,
)
from .atlas_flywheel import AdmissionFlywheelState, run_admission_flywheel
from .atlas_flywheel_runtime_context import AcceptedAtlasAdmissionRuntime
from .autonomy_live import build_live_autonomy_plan, reconcile_live_autonomy_state
from .bamf_bundle import stage_vocabulary_extension_from_source_id


from bilqis_mlx.runtime.atlas_flywheel_runtime_parts.planning import (
    _accepted_checkpoint,
    _accepted_selection,
    _candidate_frontier,
    _candidate_frontier_trust_identity,
    _persist_ready_realizations,
    _replay_current_graph,
)


def resolve_atlas_artifact_selection(identity):
    """Preserve the flywheel's patchable resolver seam after helper extraction."""
    return atlas_snapshot.resolve_atlas_artifact_selection(identity)


@dataclass(frozen=True)
class AcceptedAtlasFlywheelSupervisor:
    run_dir: Path
    parent_graph: dict | None = None
    reserve_gib: float = 100.0

    def __post_init__(self) -> None:
        if (not isinstance(self.run_dir, Path)
                or (self.parent_graph is not None
                    and not isinstance(self.parent_graph, dict))
                or not isinstance(self.reserve_gib, (int, float))
                or self.reserve_gib < 0):
            ErrorBus.raise_legacy(
                SCHOOL.BAMF_ATLAS_ADMISSION.FLYWHEEL_RUNTIME_INVALID)

    def _authority(self):
        host = AcceptedRuntimeHost(self.run_dir)
        source_authority = host.source_authority()
        lease = read_accepted_atlas_lease_v2(
            self.run_dir, source_authority=source_authority)
        if lease is None:
            ErrorBus.raise_legacy(
                SCHOOL.BAMF_ATLAS_ADMISSION.ACCEPTED_LEASE_REQUIRED)
        registry = _accepted_source_registry(self.run_dir, source_authority)
        return source_authority, lease, registry

    def load_state(self) -> AdmissionFlywheelState:
        current = read_accepted_atlas_factory_release(self.run_dir)
        selection, feature_receipt = _accepted_selection(self.run_dir)
        candidate = compile_semantic_curriculum(
            selection, SOURCE_FAMILY_ADAPTERS,
            LearnedFrontier(selection.release_sha256))
        source = issue_source_context_transition_authority(selection)
        frontier = _candidate_frontier(self.run_dir, current.release_sha256)
        graph = (
            AcceptedRuntimeHost(self.run_dir).source_context(
                source_root=None).graph
            if self.parent_graph is None else
            _replay_current_graph(current, self.parent_graph)
        )
        staged = _persist_ready_realizations(
            self.run_dir, current, candidate, frontier, graph)
        plan = build_live_autonomy_plan(current, LEGACY_SOURCE)
        ledger = reconcile_live_autonomy_state(
            self.run_dir, current, plan)
        checkpoint = _accepted_checkpoint(self.run_dir)
        _source_authority, lease, _registry = self._authority()
        delta = lease.source_approval.delta_budget_policy
        credit = read_accepted_atlas_obligation_credit(self.run_dir)
        snapshot = build_accepted_executable_snapshot(
            candidate, source.frontier, source.policy, frontier, current, staged,
            budget=PlannerBudget(
                delta.max_capabilities, delta.max_new_semantic_identities, 1000),
            admission_receipt_sha256=feature_receipt.acceptance_sha256,
            grade_labels=tuple(
                grade.grade_id for grade in current.execution_plan.grades),
        )
        closure = resolve_frontier_closure(
            snapshot, candidate.census,
            current_release=current,
            evidence_ledger=ledger,
            autonomy_plan=plan,
            checkpoint_sha256=checkpoint.sha256,
            optimizer_step=checkpoint.optimizer_step,
        )
        return AdmissionFlywheelState(
            AtlasCoverageEpoch(
                snapshot, closure, frontier, current, staged,
                accepted_credit=credit),
            AtlasLearnerEvidence(
                ledger, checkpoint.sha256, checkpoint.optimizer_step),
            plan,
        )

    def admit(self, handoff):
        current = read_accepted_atlas_factory_release(self.run_dir)
        if current.release_sha256 != handoff.receipt.predecessor_release.release_sha256:
            ErrorBus.raise_legacy(
                SCHOOL.BAMF_ATLAS_ADMISSION.FLYWHEEL_PREDECESSOR_DRIFT)
        from .generated_grade import _issue_generated_grade_admission_authority
        generated_grade_authority = _issue_generated_grade_admission_authority(
            self, handoff)
        graph = (
            AcceptedRuntimeHost(self.run_dir).source_context(
                source_root=None).graph
            if self.parent_graph is None else
            _replay_current_graph(current, self.parent_graph)
        )
        checkpoint = _accepted_checkpoint(self.run_dir)
        plan = build_live_autonomy_plan(current, LEGACY_SOURCE)
        ledger = reconcile_live_autonomy_state(self.run_dir, current, plan)
        frontier = _candidate_frontier(self.run_dir, current.release_sha256)
        source_authority, lease, registry = self._authority()
        runtime = AcceptedAtlasAdmissionRuntime(
            self.run_dir, checkpoint, graph, self.reserve_gib)
        sources, answers = live_source_registry(), live_answer_registry()
        introduced = tuple(handoff.receipt.selection.introduced_semantic_ids)
        native = None
        if introduced:
            selection, _feature_receipt = _accepted_selection(self.run_dir)
            native_semantic_ids = tuple(
                candidate_realizations.realized_atlas_semantic_id(capability_id)
                for capability_id in
                handoff.receipt.selection.introduced_capability_ids
            )
            native = stage_vocabulary_extension_from_source_id(
                self.run_dir, selection.path, selection.source_bundle_id,
                native_semantic_ids)
        legacy = AtlasAdmissionContext(
            _accepted_run_lease_identity(self.run_dir), current, frontier,
            ledger, plan, checkpoint, lease.source_approval, registry,
            sources, answers,
            runtime if introduced else None,
            native if introduced else None,
            source_authority if introduced else None,
        )
        context = AtlasAdmissionContextV2(
            legacy, self.run_dir,
            None if introduced else runtime,
            None if introduced else source_authority,
        )
        delta = AtlasDeltaEnvelopeV2(handoff, native)
        return (
            adopt_parameter_extension_atlas_successor_v2(
                context, delta, lease,
                generated_grade_authority=generated_grade_authority)
            if introduced else
            adopt_capability_only_atlas_successor_v2(
                context, delta, lease,
                generated_grade_authority=generated_grade_authority)
        )


def run_accepted_atlas_flywheel(
        run_dir: Path, parent_graph: dict, *, reserve_gib: float = 100.0,
        max_advances: int = 16):
    """Advance only through accepted cold custody; never own neural updates."""
    supervisor = AcceptedAtlasFlywheelSupervisor(
        Path(run_dir), parent_graph, reserve_gib)
    return run_admission_flywheel(
        supervisor.load_state, supervisor.admit, max_advances=max_advances)
