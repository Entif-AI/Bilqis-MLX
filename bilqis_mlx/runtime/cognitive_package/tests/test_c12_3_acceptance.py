"""C12.3 receiver-local reset, continuation, rejection, and cold-resume proof."""
from dataclasses import replace
import json
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import begin_candidate, candidate_step, resolve_candidate
from bilqis_mlx.learning.atlas_package_import import ImportSlice, prepare_package_import
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.learning.teacher_lineage import (
    initialize_teacher_lineage, restore_teacher_lineage,
)
from bilqis_mlx.learning._retention.tests.execution_fixtures import execution_provenance
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation, publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle
from bilqis_mlx.runtime.cognitive_package.tests.adoption_harness import AdoptionHarness
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    HP, NAME, acceptance, accepted_state, candidate, parent_state, publish_candidate,
    shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import (
    adaptation, selection_teacher,
)


def _receiver_history(parent, *, moment, count, age):
    optimizer = AdamWStateTree(
        parent.optimizer.parameters,
        {NAME: mx.array([[moment, moment + 1], [moment + 2, moment + 3]], dtype=mx.float32)},
        {NAME: mx.array([[moment + 4, moment + 5], [moment + 6, moment + 7]], dtype=mx.float32)},
        {NAME: mx.array([count, count + 1], dtype=mx.uint64)},
    )
    policy = PlasticityPolicy(
        parent.policy.mode,
        parent.policy.accepted_fast_since_full,
        (IdentityRowAge(0, 0, age), IdentityRowAge(0, 1, age + 1)),
        policy_version=parent.policy.policy_version,
        schema_version=parent.policy.schema_version,
    )
    return replace(parent, optimizer=optimizer, policy=policy)


class C12ReceiverResetTests(AdoptionHarness):
    def test_identical_weights_keep_receiver_local_untouched_optimizer_history(self):
        parent = parent_state()
        left = _receiver_history(parent, moment=1.0, count=11, age=5)
        right = _receiver_history(parent, moment=21.0, count=31, age=6)
        parameters = {
            NAME: mx.array([[9.0, -0.25], [1.0, 2.0]], dtype=mx.float32),
        }
        changed = (ImportSlice(NAME, 0, 1),)

        first = prepare_package_import(left, parameters, changed).candidate
        second = prepare_package_import(right, parameters, changed).candidate

        np.testing.assert_array_equal(
            np.asarray(first.optimizer.parameters[NAME]),
            np.asarray(second.optimizer.parameters[NAME]),
        )
        for candidate_state in (first, second):
            self.assertEqual(float(np.asarray(candidate_state.optimizer.m[NAME])[0, 0]), 0.0)
            self.assertEqual(float(np.asarray(candidate_state.optimizer.v[NAME])[0, 0]), 0.0)
            self.assertEqual(int(np.asarray(candidate_state.optimizer.update_counts[NAME])[0]), 0)
            self.assertEqual(candidate_state.policy.accepted_fast_since_full, 0)
            self.assertEqual(candidate_state.policy.mode, parent.policy.mode)
            self.assertEqual(candidate_state.policy.row_ages[0].accepted_age, 0)

        self.assertNotEqual(
            float(np.asarray(first.optimizer.m[NAME])[1, 0]),
            float(np.asarray(second.optimizer.m[NAME])[1, 0]),
        )
        self.assertNotEqual(
            int(np.asarray(first.optimizer.update_counts[NAME])[1]),
            int(np.asarray(second.optimizer.update_counts[NAME])[1]),
        )
        self.assertEqual(first.policy.row_ages[1].accepted_age, 6)
        self.assertEqual(second.policy.row_ages[1].accepted_age, 7)

    def test_native_step_then_rejected_candidate_cold_resumes_exact_accepted_state(self):
        screened, receipt = self.screened()
        imported_pointer = self.adopt(screened, receipt)
        with shape_patch():
            imported = load_bamf_generation(self.run / "bamf-state.json")

        transaction = begin_candidate(imported.retained_state)
        execution = execution_provenance(
            transaction.parent, rows=(0,), candidate_step=1, extents=imported.extents,
        )
        self.assertEqual(
            execution.parent_manifest_sha256,
            imported_pointer["manifest_sha256"])
        self.assertEqual(execution.parent_optimizer_step,
                         imported.retained_state.optimizer_step)
        self.assertEqual(imported.transition["kind"], "PACKAGE_IMPORT")
        self.assertEqual(
            imported.transition["package_sha256"],
            screened.candidate.package.digest)
        self.assertEqual(
            imported.transition["reset_policy_sha256"],
            screened.transaction.reset_policy_sha256)
        with shape_patch():
            transaction = candidate_step(
                transaction,
                {NAME: mx.array([[1.0, 1.0], [0.0, 0.0]], dtype=mx.float32)},
                execution, HP, spec=imported.topology, extents=imported.extents,
                loss_bearing=True, max_norm=1.0,
            )
        accepted_state = resolve_candidate(transaction, accepted=True)
        successor = candidate(
            accepted_state,
            generation=imported.generation + 1,
            parent=imported_pointer["manifest_sha256"],
        )
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            accepted_pointer = publish_candidate(self.run, successor)
            accepted = load_bamf_generation(self.run / "bamf-state.json")

        expected = candidate_identity_digest(accepted.retained_state)
        later = begin_candidate(accepted.retained_state)
        later_execution = execution_provenance(
            later.parent, rows=(0,), candidate_step=1, extents=accepted.extents,
        )
        with shape_patch():
            later = candidate_step(
                later,
                {NAME: mx.array([[4.0, -3.0], [0.0, 0.0]], dtype=mx.float32)},
                later_execution, HP, spec=accepted.topology, extents=accepted.extents,
                loss_bearing=True, max_norm=1.0,
            )
        rejected = resolve_candidate(later, accepted=False)
        self.assertEqual(candidate_identity_digest(rejected), expected)

        pointer_after_reject = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(
            pointer_after_reject["manifest_sha256"],
            accepted_pointer["manifest_sha256"],
        )
        with shape_patch():
            cold = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(candidate_identity_digest(cold.retained_state), expected)
        self.assertEqual(
            cold.retained_state.optimizer_step,
            imported.retained_state.optimizer_step + 1,
        )

    def test_mature_recipient_rebinds_its_own_teacher_lineage_on_import(self):
        with shape_patch():
            native = accepted_state(
                self.initial.retained_state, self.initial.extents)
            successor = derive_successor_bundle(
                self.initial, native,
                parent_manifest_sha256=self.pointer["manifest_sha256"],
                delivery_events=(
                    {"event": "C12_MATURE_RECIPIENT", "optimizer_step": 1},
                ))
        mature_teacher = initialize_teacher_lineage(
            {"teacher": selection_teacher()},
            {
                "schema": "bilqis.bamf.student-reference/v1",
                "student_sha256": candidate_identity_digest(native),
                "region": "c12-mature-recipient-region",
            },
            adaptation(), prior_region="legacy-region",
            next_seed=91, cursor="lesson:recipient",
        )
        mature = replace(
            successor,
            provenance=replace(
                successor.provenance,
                teacher_identity=mature_teacher.teacher_identity,
                teacher_epoch=mature_teacher.teacher_epoch),
            teacher_state=dict(mature_teacher.teacher_state),
        )
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            self.pointer = publish_bamf_generation(
                self.run, mature,
                acceptance=acceptance(
                    mature, parent=self.initial.retained_state),
                reserve_gib=0.)
            self.initial = load_bamf_generation(self.run / "bamf-state.json")

        self.state = self.initial.retained_state
        array = np.asarray(self.state.optimizer.parameters[NAME], dtype="<f4")
        from bilqis_mlx.runtime.cognitive_package import (
            PackageBinding, ReceiverTensor, receiver_parameter_schema_digest,
            receiver_weight_digest,
        )
        self.tensor = ReceiverTensor(NAME, array.shape, array.tobytes())
        self.binding = PackageBinding(
            receiver_weight_digest((self.tensor,)),
            receiver_parameter_schema_digest((self.tensor,)),
            self.initial.topology.digest, self.initial.provenance.release_digest,
            self.initial.extents.active_semantic_digest,
            self.initial.extents.factor_map_digest,
            self.initial.extents.motif_key_map_digest)
        before = restore_teacher_lineage(self.initial.teacher_state)
        old = self.initial.teacher_state["c03_lineage"]

        screened, receipt = self.screened()
        self.adopt(screened, receipt)
        with shape_patch():
            imported = load_bamf_generation(self.run / "bamf-state.json")
        restored = restore_teacher_lineage(imported.teacher_state)
        new = imported.teacher_state["c03_lineage"]
        self.assertEqual(imported.teacher_state["teacher_epoch"], 1)
        self.assertEqual(imported.teacher_state["next_seed"], 91)
        self.assertEqual(imported.teacher_state["cursor"], "lesson:recipient")
        self.assertEqual(new["prior_teacher"], old["current_teacher"])
        self.assertEqual(new["source_teacher_sha256"], old["source_teacher_sha256"])
        self.assertEqual(new["current_teacher"]["grade_stats"], {})
        self.assertEqual(
            new["current_teacher"]["causal_experiment"]["student_policy_epoch"][
                "student_sha256"],
            candidate_identity_digest(imported.retained_state))
        self.assertNotEqual(restored.student_sha256, before.student_sha256)
        self.assertEqual(
            restored.student_sha256,
            candidate_identity_digest(imported.retained_state))
        self.assertEqual(
            imported.provenance.teacher_identity,
            imported.teacher_state["teacher_identity"])
        self.assertEqual(
            imported.provenance.teacher_epoch,
            imported.teacher_state["teacher_epoch"])
