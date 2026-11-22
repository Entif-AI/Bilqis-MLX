"""Shared fixture helpers for native BAMF -> Model Forensics CP07 tests."""
from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.compatibility import historical_teacher_policy
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.runtime.accepted_teacher_custody import (
    derive_c03_successor_bundle, select_accepted_teacher_visit,
)
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.bamf_operator.session import _resource_observation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.acceptance._generation_acceptance_support import (
    GenerationAcceptanceFixture,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, accepted_state, shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import (
    adaptation, selection_teacher,
)


class NativeSourceFixture(GenerationAcceptanceFixture):
    """Small source-authenticated lineage used across CP07 production tests."""

    def publish(self, source, **kwargs):
        kwargs.setdefault("reserve_gib", 0)
        return super().publish(source, **kwargs)

    def bound_native_visit(self, parent, *, capability="A.REJECT"):
        school = SimpleNamespace(
            stage="RECOVERY_1",
            current_student=SimpleNamespace(
                sha256=candidate_identity_digest(parent.retained_state)),
        )
        bootstrap = {}
        if "c03_lineage" not in parent.teacher_state:
            bootstrap = {
                "legacy_receipt": {"teacher": selection_teacher()},
                "adaptation": adaptation(),
                "prior_region": "legacy-region",
            }
        with shape_patch():
            bound, _policy, _metadata = select_accepted_teacher_visit(
                self.run, historical_teacher_policy, school, random.Random(17),
                Settings(), "factory/7", {}, "A", capability_id=capability,
                total_capabilities=20, **bootstrap)
        return bound

    def native_visit(self, parent, *, capability="A.REJECT"):
        return self.bound_native_visit(parent, capability=capability).identity

    def successor(self):
        parent = self.parent()
        source = self.source()
        visit = self.bound_native_visit(parent, capability="A.NATIVE")
        resource = _resource_observation(self.run, SimpleNamespace(realized_cost={
            "wall_seconds": 30.0,
            "optimizer_steps": 1,
            "c08_memory_budget_bytes": 64 * 1024 ** 3,
        }))
        with shape_patch():
            return derive_c03_successor_bundle(
                self.run, source.retained_state, visit,
                next_seed=visit.identity.selection_seed + 1,
                cursor=visit.identity.visit_id,
                delivery_events=({
                "event": "BAMF_C16_3_ACCEPTED",
                "optimizer_step": source.retained_state.optimizer_step,
                "capability": "A.NATIVE",
                "resource": resource,
                },),
            )

    def publish_successor(self):
        source = self.successor()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = self.publish(source, acceptance=self.binding(source))
        return source, pointer

    def publish_next_successor(self, capability):
        """Publish a second accepted visit against the actual current parent."""
        with shape_patch():
            parent = load_bamf_generation(self.run / "bamf-state.json")
        retained = accepted_state(parent.retained_state, parent.extents, parent.topology)
        visit = self.bound_native_visit(parent, capability=capability)
        resource = _resource_observation(self.run, SimpleNamespace(realized_cost={
            "wall_seconds": 20.0,
            "optimizer_steps": 1,
            "c08_memory_budget_bytes": 64 * 1024 ** 3,
        }))
        with shape_patch():
            source = derive_c03_successor_bundle(
                self.run, retained, visit,
                next_seed=visit.identity.selection_seed + 1,
                cursor=visit.identity.visit_id,
                delivery_events=({
                    "event": "BAMF_C16_3_ACCEPTED",
                    "optimizer_step": retained.optimizer_step,
                    "capability": capability,
                    "resource": resource,
                },),
            )
        pointer = self.publish(
            source, acceptance=acceptance(source, parent=parent.retained_state))
        return source, pointer


__all__ = ("NativeSourceFixture",)
