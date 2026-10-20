"""Human-run bridge from the pure autonomy planner to admitted live sources.

Everything here is neural-inert.  The human trainer owns optimizer mutation,
checkpoint publication, and the grade scheduler; this module only compiles the
source-backed plan, restores its durable ledger, and measures evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
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
    reconcile_successor_evidence,
)
from ..factory.evidence import measure_evidence
from ..factory.teaching import content_digest
from ..factory.model import FactoryRelease
from ..registry_ast import load_registry
from ..semantic_coverage import (
    audit_pinned_micro_generator,
    discover_composition_obligations,
)
from ..source_adapters.school import live_source_registry
from ..curriculum.scheduler import (
    SchoolState, assessment_capabilities, next_capability, verify_state, visit)
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
    if not isinstance(release, FactoryRelease):
        source_registry = live_source_registry()
        return compile_autonomy_plan(
            release, supplemental_evidence=source_registry.evidence_dependencies(
                None, release=release))
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
        # A v2 successor may inherit only projection-stable evidence.  Recover
        # the predecessor from its immutable factory artifact so a crash between
        # release adoption and in-memory refresh does not erase valid evidence.
        from ..factory.executable_release import ExecutableFactoryRelease
        if isinstance(release, ExecutableFactoryRelease):
            previous_sha256 = raw.get("factory_release_sha256")
            previous_file = root / "factory-releases" / (
                str(previous_sha256) + ".json")
            if previous_file.is_file() and not previous_file.is_symlink():
                previous_payload = json.loads(
                    previous_file.read_text(encoding="utf-8"))
                if previous_payload.get("schema") == release.schema:
                    from .admission import (
                        _read_executable_factory_release_artifact)
                    previous_release = _read_executable_factory_release_artifact(
                        root, {
                            "factory_release_sha256": previous_sha256,
                            "factory_release_file": (
                                "factory-releases/" + previous_sha256 + ".json"),
                        })
                    old_plan, old_ledger = read_autonomy_state(
                        root, previous_release)
                    ledger = reconcile_successor_evidence(
                        previous_release, release, old_ledger,
                        previous_plan=old_plan, current_plan=plan)
                    persist_autonomy_state(
                        root, release, plan=plan, ledger=ledger)
                    return ledger
        # Legacy releases have no per-capability projection closure.  A new
        # admitted release therefore owns a fresh evidence epoch; immutable
        # predecessor snapshots remain under autonomy/states for audit.
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


def reroute_failed_teaching(
    release: FactoryRelease, school: SchoolState, capability_id: str,
) -> SchoolState:
    """Neural-inertly put a still-legal failed proof back at queue head.

    A retention rejection may roll the student back while the ordinary school
    visit has already advanced its queue.  Autonomy must not silently teach the
    new queue head while its failed evidence still demands remediation.
    """
    from ..factory.schedule import schedule_program_from_executable_release
    program = (release.course if isinstance(release, FactoryRelease) else
               schedule_program_from_executable_release(release))
    verify_state(program, school)
    if capability_id not in assessment_capabilities(program, school):
        raise ValueError("AUTONOMY_TEACHING_REROUTE_OUTSIDE_SCHEDULER_SCOPE")
    queue = (capability_id, *(
        item for item in school.queue if item != capability_id))
    rerouted = replace(school, queue=queue)
    verify_state(program, rerouted)
    return rerouted


def advance_if_scheduled_evidence_complete(
    release: FactoryRelease, plan: AutonomyPlan, ledger: EvidenceLedger,
    school: SchoolState, capability_id: str,
) -> SchoolState:
    """Treat complete evidence as a zero-update scheduled visit when aligned."""
    if not scheduled_teaching_matches(school, capability_id):
        return school
    if capability_id not in set(
            evidence_complete_capabilities(
                release, ledger, plan=plan,
                current_checkpoint_sha256=school.current_student.sha256,
                current_optimizer_step=school.current_student.optimizer_step)):
        return school
    from ..factory.schedule import schedule_program_from_executable_release
    program = (release.course if isinstance(release, FactoryRelease) else
               schedule_program_from_executable_release(release))
    return visit(program, school, capability_id, school.current_student)


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
        try:
            ledger = reconcile_successor_evidence(
                self.release, release, self.ledger,
                previous_plan=self.plan, current_plan=plan)
            persist_autonomy_state(
                self.run_dir, release, plan=plan, ledger=ledger)
        except TypeError:
            # Legacy v1 releases have no per-capability projection contract.
            # They start a fresh evidence epoch; v2 successor drift propagates.
            ledger = reconcile_live_autonomy_state(
                self.run_dir, release, plan)
        self.release, self.plan, self.ledger = release, plan, ledger

    def action(self, checkpoint) -> AutonomyAction:
        return next_action(self.release, self.ledger, plan=self.plan,
                           current_checkpoint_sha256=checkpoint.sha256,
                           current_optimizer_step=checkpoint.optimizer_step)

    def measure(self, graph, work: CurriculumWorkItem, *, checkpoint: dict,
                seed: int, predictor):
        evidence = measure_live_evidence(
            self.source_root, graph, self.release, work,
            checkpoint=checkpoint, seed=seed, predictor=predictor)
        self.ledger = record_evidence(
            self.release, self.ledger, evidence, plan=self.plan,
            current_checkpoint_sha256=checkpoint["sha256"],
            current_optimizer_step=checkpoint["optimizer_step"])
        persist_autonomy_state(
            self.run_dir, self.release, plan=self.plan, ledger=self.ledger)
        return evidence

    def record_teaching(self, receipt: TeachingReceipt, *, parent_checkpoint) -> None:
        self.ledger = record_teaching_intervention(
            self.release, self.ledger, receipt, plan=self.plan,
            current_checkpoint_sha256=parent_checkpoint.sha256,
            current_optimizer_step=parent_checkpoint.optimizer_step)
        persist_autonomy_state(
            self.run_dir, self.release, plan=self.plan, ledger=self.ledger)

    def recover_teaching(
        self, school_receipt: dict, checkpoint,
    ) -> TeachingReceipt | None:
        """Reconcile a committed teaching visit into the autonomy ledger.

        The trainer commits the model+AdamW checkpoint and its delivery outbox
        before this ledger write.  If the process dies in that narrow window,
        the durable outbox plus immutable specimen file are sufficient to
        rebuild exactly the missing intervention on restart.
        """
        outbox = school_receipt.get("delivery_outbox")
        if not isinstance(outbox, list):
            return None
        for event in reversed(outbox):
            delivery = event.get("autonomy_teaching")
            if not isinstance(delivery, dict):
                continue
            if (event.get("recovered_at_student_sha256") != checkpoint.sha256 or
                    event.get("optimizer_step") != checkpoint.optimizer_step):
                continue
            capability = event.get("capability")
            if not isinstance(capability, str) or not capability:
                raise ValueError("AUTONOMY_TEACHING_RECOVERY_CAPABILITY_INVALID")
            specimen_file = delivery.get("specimen_file")
            digest = delivery.get("specimen_content_sha256")
            expected_file = "autonomy/teaching/" + str(digest) + ".json"
            if specimen_file != expected_file:
                raise ValueError("AUTONOMY_TEACHING_RECOVERY_SPECIMEN_PATH_DRIFT")
            path = self.run_dir / expected_file
            if (path.parent.is_symlink() or path.is_symlink() or
                    not path.is_file()):
                raise ValueError("AUTONOMY_TEACHING_RECOVERY_SPECIMEN_MISSING")
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("rows") if isinstance(payload, dict) else None
            if (not isinstance(rows, list) or content_digest(rows) != digest or
                    tuple(dict.fromkeys(row.get("id") for row in rows)) !=
                    tuple(delivery.get("specimen_ids", ()))):
                raise ValueError("AUTONOMY_TEACHING_RECOVERY_SPECIMEN_DRIFT")

            obligations = {
                item.obligation_id: item
                for item in self._obligations_for_capability(capability)
            }
            failed = next((
                receipt for receipt in reversed(self.ledger.receipts)
                if (not receipt.passed and
                    receipt.obligation_id in obligations and
                    receipt.optimizer_step < checkpoint.optimizer_step)
            ), None)
            if failed is None:
                continue
            existing = next((
                item for item in self.ledger.interventions
                if (item.obligation_id == failed.obligation_id and
                    item.checkpoint_sha256 == checkpoint.sha256 and
                    item.specimen_content_sha256 == digest)
            ), None)
            if existing is not None:
                return existing
            intervention_id = hashlib.sha256(json.dumps({
                "run_id": school_receipt.get("run_id"),
                "generation": school_receipt.get("generation"),
                "obligation": failed.obligation_id,
                "parent": failed.checkpoint_sha256,
                "student": checkpoint.sha256,
                "optimizer_step": checkpoint.optimizer_step,
            }, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            intervention = TeachingReceipt(
                obligation_id=failed.obligation_id,
                intervention_id=intervention_id,
                teaching_option_id=delivery["option_id"],
                selected_provider_id=delivery["provider_id"],
                provider_implementation_sha256=(
                    delivery["provider_implementation_sha256"]),
                specimen_ids=tuple(delivery["specimen_ids"]),
                specimen_content_sha256=digest,
                variation_axes=tuple(delivery["variation_axes"]),
                optimizer_step_delta=(
                    checkpoint.optimizer_step - failed.optimizer_step),
                parent_checkpoint_sha256=failed.checkpoint_sha256,
                parent_optimizer_step=failed.optimizer_step,
                checkpoint_sha256=checkpoint.sha256,
                optimizer_step=checkpoint.optimizer_step,
            )
            self.ledger = record_teaching_intervention(
                self.release, self.ledger, intervention, plan=self.plan,
                current_checkpoint_sha256=failed.checkpoint_sha256,
                current_optimizer_step=failed.optimizer_step)
            persist_autonomy_state(
                self.run_dir, self.release, plan=self.plan, ledger=self.ledger)
            return intervention
        return None

    def _obligations_for_capability(self, capability_id: str):
        from ..factory.autonomy import obligations_for_capability
        return obligations_for_capability(
            self.release, capability_id, plan=self.plan)

    def evidence_complete(self, checkpoint) -> tuple[str, ...]:
        return evidence_complete_capabilities(
            self.release, self.ledger, plan=self.plan,
            current_checkpoint_sha256=checkpoint.sha256,
            current_optimizer_step=checkpoint.optimizer_step)

    def advance_if_complete(
        self, school: SchoolState, capability_id: str,
    ) -> SchoolState:
        return advance_if_scheduled_evidence_complete(
            self.release, self.plan, self.ledger, school, capability_id)

    def reroute_teaching(
        self, school: SchoolState, capability_id: str,
    ) -> SchoolState:
        return reroute_failed_teaching(self.release, school, capability_id)
