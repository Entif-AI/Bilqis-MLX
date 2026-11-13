"""C07.1b executor revalidates context before native or legacy commit."""
from dataclasses import asdict, replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.runtime.jit_adoption import (
    _authenticate_native_staged_candidate, _execute_prepared_successor_adoption,
)
from bilqis_mlx.runtime.tests.admission.atlas.adoption.atlas_adoption_executor_support import (
    AtlasAdoptionExecutorFixture,
)


class AtlasAdoptionExecutorTests(AtlasAdoptionExecutorFixture, unittest.TestCase):
    def test_native_candidate_preflight_requires_exact_b13_parent_and_a02_anchors(self):
        parent, staged = self._native_parent_and_candidate()
        owner_staged = self._a02_staged(staged)
        parent_feature = SimpleNamespace(
            generation_manifest_sha256="a" * 64, digest="b" * 64)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, "a" * 64)), patch(
                "bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt",
                return_value=parent_feature):
            self.assertIs(
                _authenticate_native_staged_candidate(self.root, owner_staged),
                owner_staged.candidate)
            with self.assertRaises(BilqisError) as failure:
                _authenticate_native_staged_candidate(
                    self.root, SimpleNamespace(candidate=staged))
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_A02_STAGED_EXTENSION_INVALID")

    def test_native_candidate_preflight_rejects_parent_drift_before_mutation(self):
        parent, staged = self._native_parent_and_candidate()
        parent_feature = SimpleNamespace(
            generation_manifest_sha256="a" * 64, digest="b" * 64)
        owner_staged = self._a02_staged(
            replace(staged, parent_manifest_sha256="d" * 64))
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, "a" * 64)), patch(
                "bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt",
                return_value=parent_feature):
            with self.assertRaises(BilqisError) as failure:
                _authenticate_native_staged_candidate(self.root, owner_staged)
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_ATLAS_ACCEPTED_PARENT_DRIFT")

    def test_executor_rechecks_saved_checkpoint_before_native_commit(self):
        plan, ledger, proposal = self._proposal(self.staged)
        fixture = self.fixture.fixture
        stale = replace(self.checkpoint, optimizer_step=1)
        self.receipt["school"]["current_student"] = {
            **self.receipt["school"]["current_student"], "optimizer_step": 1}
        with self.admitted_boundary(), patch.object(
                release_adoption, "_adopt_prepared_successor",
                side_effect=AssertionError("stale executor entered commit")):
            with self.assertRaises(BilqisError) as failure:
                _execute_prepared_successor_adoption(
                    self._runtime(), frontier=self.frontier, current=self.current,
                    ledger=ledger, plan=plan, checkpoint=self.checkpoint,
                    proposal=proposal, staged=(self.staged,),
                    source_registry=fixture.registry,
                    answer_registry=fixture.answers)
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_ATLAS_RUNTIME_CONTEXT_CHANGED")
        self.assertNotEqual(stale, self.checkpoint)

    def test_native_same_grade_growth_commits_once_without_optimizer_update(self):
        import numpy as np
        from bilqis_mlx import state_dag

        native = self.prepare_native_same_grade_growth()
        self.staged = native.staged
        _, release_file, admission = (
            release_adoption._runtime_admission._executable_factory_admission(
                self.root, self.current, self.checkpoint,
                release_adoption._runtime_state._fingerprint(self.graph),
                self.graph))
        self.receipt.update(
            factory_release_sha256=self.current.release_sha256,
            factory_release_file=release_file,
            factory_release_schema=self.current.schema,
            factory_admission_v2=asdict(admission))
        plan, ledger, proposal = self._proposal(self.staged)
        fixture = self.fixture.fixture
        old_weights = {
            name: np.array(value) for name, value in self.parameters.items()}
        with patch.object(
                release_adoption._compatibility_executable_projection,
                "legacy_course_for_profile",
                return_value=SimpleNamespace(version="fixture")), patch(
                "bilqis_mlx.factory.candidate_realizations.admitted_candidate_graph",
                return_value=native.graph), patch(
                "bilqis_mlx.learning.student_ops._predictions",
                side_effect=lambda _mx, _parameters, rows, *_:
                    {row["id"]: row["gold"] for row in rows}), patch.object(
                native.optim.AdamW, "update",
                side_effect=AssertionError("neural optimizer update")):
            result = _execute_prepared_successor_adoption(
                self._runtime(native.mx), frontier=self.frontier,
                current=self.current, ledger=ledger, plan=plan,
                checkpoint=self.checkpoint, proposal=proposal,
                staged=(self.staged,), source_registry=fixture.registry,
                answer_registry=fixture.answers)

        self.assertEqual(
            result.receipt["factory_release_sha256"],
            self.staged.successor.release_sha256)
        self.assertEqual(state_dag.read_current(self.root), result.receipt)
        self.assertEqual(int(result.optimizer.state["step"].item()), 7)
        self.assertEqual(int(self.optimizer.state["step"].item()), 7)
        for name, old in old_weights.items():
            active = (result.parameters[name][:native.old_count]
                      if name == "embedding.weight" else result.parameters[name])
            np.testing.assert_array_equal(np.asarray(active), old)
            np.testing.assert_array_equal(np.asarray(self.parameters[name]), old)


if __name__ == "__main__":
    unittest.main()
