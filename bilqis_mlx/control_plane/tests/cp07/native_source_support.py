"""Shared fixture helpers for native BAMF -> Mission Control CP07 tests."""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.teacher_visit_identity import (
    TeacherVisitIdentity, record_teacher_visit_receipt,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.acceptance._generation_acceptance_support import (
    GenerationAcceptanceFixture,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch


class NativeSourceFixture(GenerationAcceptanceFixture):
    """Small source-authenticated lineage used across CP07 production tests."""

    def native_visit(self, parent, *, capability="A.REJECT", policy="policy:native"):
        state = parent.teacher_state
        visit = TeacherVisitIdentity(
            parent.run_identity.digest, parent.run_identity.run_seed,
            parent.generation, self._parent_pointer["manifest_sha256"],
            state["teacher_identity"], state["teacher_epoch"],
            candidate_identity_digest(parent.retained_state),
            state["next_seed"], state["cursor"], capability, policy,
        )
        record_teacher_visit_receipt(visit)
        return visit

    def successor(self):
        parent = self.parent()
        source = self.source()
        visit = self.native_visit(parent, capability="A.NATIVE")
        return replace(
            source,
            teacher_state={**source.teacher_state, "last_visit": visit.to_record()},
            outbox=({
                "event": "BAMF_C16_3_ACCEPTED",
                "optimizer_step": source.retained_state.optimizer_step,
                "capability": "A.NATIVE",
            },),
        )

    def publish_successor(self):
        source = self.successor()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = self.publish(source, acceptance=self.binding(source))
        return source, pointer


__all__ = ("NativeSourceFixture",)
