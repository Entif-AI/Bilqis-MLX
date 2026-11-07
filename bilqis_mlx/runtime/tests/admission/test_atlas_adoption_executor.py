"""C07.1b concrete executor uses the native prepared-successor transaction."""
from dataclasses import asdict, replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.runtime.jit_adoption import (
    _PreparedSuccessorRuntime, _execute_prepared_successor_adoption,
)
from bilqis_mlx.runtime.tests.admission.prepared_successor_fixtures import (
    PreparedSuccessorFixture,
)


class AtlasAdoptionExecutorTests(PreparedSuccessorFixture, unittest.TestCase):
    def _proposal(self, staged):
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        proposal = propose_curriculum_delta(
            self.frontier, self.current, ledger, plan,
            self.checkpoint.sha256, self.checkpoint.optimizer_step,
            candidate_bindings=(staged.binding,))
        return plan, ledger, proposal

    def _runtime(self, mx=None):
        return _PreparedSuccessorRuntime(
            mx, self.root, self.receipt, None, None, self.graph,
            self.parameters, self.optimizer, 0.)

    def test_executor_rechecks_saved_checkpoint_before_native_commit(self):
        plan, ledger, proposal = self._proposal(self.staged)
        fixture = self.fixture.fixture
        stale = replace(self.checkpoint, optimizer_step=1)
        self.receipt["school"]["current_student"] = {
            **self.receipt["school"]["current_student"], "optimizer_step": 1}
        with self.admitted_boundary(), patch.object(
                release_adoption, "_adopt_prepared_successor",
                side_effect=AssertionError("stale executor entered commit")):
            with self.assertRaisesRegex(
                    ValueError, "JIT_ADOPTION_RUNTIME_CONTEXT_CHANGED"):
                _execute_prepared_successor_adoption(
                    self._runtime(), frontier=self.frontier, current=self.current,
                    ledger=ledger, plan=plan, checkpoint=self.checkpoint,
                    proposal=proposal, staged=(self.staged,),
                    source_registry=fixture.registry,
                    answer_registry=fixture.answers)
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
            factory_admission_v2=asdict(admission),
        )
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
