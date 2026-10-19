"""Human-run bridge from the pure autonomy planner to admitted live sources.

Everything here is neural-inert.  The human trainer owns optimizer mutation,
checkpoint publication, and the grade scheduler; this module only compiles the
source-backed plan, restores its durable ledger, and measures evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ..curriculum_compiler import compile_ast
from ..factory.autonomy import (
    AutonomyPlan,
    AutonomyAction,
    CurriculumWorkItem,
    EvidenceLedger,
    TeachingReceipt,
    compile_autonomy_plan,
    evidence_complete_capabilities,
    initial_evidence_ledger,
    next_action,
    rebind_evidence_ledger,
    record_evidence,
    record_teaching_intervention,
)
from ..factory.evidence import measure_evidence
from ..factory.model import FactoryRelease
from ..registry_ast import load_registry
from ..semantic_coverage import (
    audit_pinned_micro_generator,
    discover_composition_obligations,
)
from ..source_adapters.school import live_source_registry
from ..curriculum.scheduler import SchoolState, next_capability, visit
from .autonomy_state import (
    persist_autonomy_state,
    read_autonomy_state,
)


REGISTRY_SNAPSHOT = (
    Path(__file__).resolve().parents[2]
    / "docs/provenance/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json"
)


def build_live_autonomy_plan(
    release: FactoryRelease, source_root: Path,
) -> AutonomyPlan:
    """Compile the strongest currently source-proven autonomy plan."""
    release.verify()
    registry = load_registry(REGISTRY_SNAPSHOT)
    source_registry = live_source_registry()
    discovered = discover_composition_obligations(
        compile_ast(release.course), registry)
    if any(
            edge["status"] == "AWAITING_SOURCE_WITNESS"
            for edge in discovered["obligations"]):
        discovered = audit_pinned_micro_generator(
            discovered, Path(source_root), max_rounds=8, each=24)
    return compile_autonomy_plan(
        release, discovered,
        supplemental_evidence=source_registry.evidence_dependencies(
            release.course),
    )


def reconcile_live_autonomy_state(
    run_dir: Path, release: FactoryRelease, plan: AutonomyPlan,
) -> EvidenceLedger:
    """Restore same-release autonomy state or initialize a new release epoch."""
    root = Path(run_dir)
    pointer = root / "autonomy/current.json"
    if not pointer.exists():
        ledger = initial_evidence_ledger(release, plan=plan)
        persist_autonomy_state(root, release, plan=plan, ledger=ledger)
        return ledger
    if pointer.is_symlink() or not pointer.is_file():
        raise ValueError("AUTONOMY_STATE_POINTER_UNSAFE")
    raw = json.loads(pointer.read_text())
    if raw.get("factory_release_sha256") != release.release_sha256:
        # A new admitted release owns a fresh evidence epoch.  Immutable prior
        # snapshots remain in autonomy/states for audit and recovery.
        ledger = initial_evidence_ledger(release, plan=plan)
        persist_autonomy_state(root, release, plan=plan, ledger=ledger)
        return ledger
    old_plan, ledger = read_autonomy_state(root, release)
    if old_plan.digest() != plan.digest():
        ledger = rebind_evidence_ledger(
            release, ledger, old_plan=old_plan, new_plan=plan)
        persist_autonomy_state(root, release, plan=plan, ledger=ledger)
    return ledger


def measure_live_evidence(
    source_root, graph, release: FactoryRelease, work: CurriculumWorkItem, *,
    checkpoint: dict, seed: int, predictor,
):
    """Measure one obligation against the exact durable checkpoint supplied."""
    return measure_evidence(
        source_root, graph, release, live_source_registry(), work.obligation,
        checkpoint=checkpoint, seed=seed, predictor=predictor)


def scheduled_teaching_matches(
    school: SchoolState, capability_id: str,
) -> bool:
    """Never target optimizer work outside the scheduler's legal queue head."""
    return next_capability(school) == capability_id


def advance_if_scheduled_evidence_complete(
    release: FactoryRelease, plan: AutonomyPlan, ledger: EvidenceLedger,
    school: SchoolState, capability_id: str,
) -> SchoolState:
    """Treat complete evidence as a zero-update scheduled visit when aligned."""
    if not scheduled_teaching_matches(school, capability_id):
        return school
    if capability_id not in set(
            evidence_complete_capabilities(release, ledger, plan=plan)):
        return school
    return visit(
        release.course, school, capability_id, school.current_student)


@dataclass
class LiveAutonomySession:
    """Durable neural-inert autonomy state for one human-operated trainer."""

    run_dir: Path
    source_root: Path
    release: FactoryRelease
    plan: AutonomyPlan
    ledger: EvidenceLedger

    @classmethod
    def open(cls, run_dir: Path, source_root: Path, release: FactoryRelease):
        plan = build_live_autonomy_plan(release, source_root)
        ledger = reconcile_live_autonomy_state(run_dir, release, plan)
        return cls(Path(run_dir), Path(source_root), release, plan, ledger)

    def refresh_release(self, release: FactoryRelease) -> None:
        if release.release_sha256 == self.release.release_sha256:
            return
        plan = build_live_autonomy_plan(release, self.source_root)
        ledger = reconcile_live_autonomy_state(self.run_dir, release, plan)
        self.release, self.plan, self.ledger = release, plan, ledger

    def action(self) -> AutonomyAction:
        return next_action(self.release, self.ledger, plan=self.plan)

    def measure(self, graph, work: CurriculumWorkItem, *, checkpoint: dict,
                seed: int, predictor):
        evidence = measure_live_evidence(
            self.source_root, graph, self.release, work,
            checkpoint=checkpoint, seed=seed, predictor=predictor)
        self.ledger = record_evidence(
            self.release, self.ledger, evidence, plan=self.plan)
        persist_autonomy_state(
            self.run_dir, self.release, plan=self.plan, ledger=self.ledger)
        return evidence

    def record_teaching(self, receipt: TeachingReceipt) -> None:
        self.ledger = record_teaching_intervention(
            self.release, self.ledger, receipt, plan=self.plan)
        persist_autonomy_state(
            self.run_dir, self.release, plan=self.plan, ledger=self.ledger)

    def evidence_complete(self) -> tuple[str, ...]:
        return evidence_complete_capabilities(
            self.release, self.ledger, plan=self.plan)

    def advance_if_complete(
        self, school: SchoolState, capability_id: str,
    ) -> SchoolState:
        return advance_if_scheduled_evidence_complete(
            self.release, self.plan, self.ledger, school, capability_id)
