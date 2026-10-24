"""Deterministic prepared-cutover contract; transaction owners are isolated seams."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.factory.tests.test_candidate_staging import CandidateStagingFixture
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.runtime.jit_adoption import resolve_ready_candidate


class PreparedSuccessorFixture(CandidateStagingFixture):
    def setUp(self):
        super().setUp()
        self.staged = self.stage()
        self.graph = self.fixture.fixture.graph
        self.checkpoint = Checkpoint("e" * 64, "bundles/fixture", 0, True)
        self.program = schedule_program_from_executable_release(self.current)
        self.receipt = {"school": asdict(start_new(self.program, self.checkpoint))}
        self.parameters = {"weights": [1., 2.]}
        self.optimizer = SimpleNamespace(
            state={"step": 0}, update=Mock(side_effect=AssertionError("neural update")))
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @contextmanager
    def admitted_boundary(self):
        with patch.object(release_adoption._runtime_admission,
                "_require_executable_factory_admission", return_value=self.current), \
                patch.object(release_adoption._factory_executable_release,
                    "compile_executable_factory_release", side_effect=AssertionError("recompiled")), \
                patch.object(release_adoption._factory_executable_release,
                    "compile_successor_profile_release", side_effect=AssertionError("recompiled")):
            yield

    def adopt(self, staged=None):
        return release_adoption._adopt_prepared_successor(
            None, self.root, self.receipt, None, None, self.graph,
            self.parameters, self.optimizer, self.staged if staged is None else staged,
            reserve_gib=100.)


class PreparedSuccessorTests(PreparedSuccessorFixture, unittest.TestCase):
    def test_same_graph_routes_the_exact_sealed_successor_without_compiling(self):
        result_receipt = {"prepared": True}
        before = deepcopy((self.parameters, self.optimizer.state, self.receipt))
        with self.admitted_boundary(), patch.object(release_adoption,
                "_adopt_executable_profile", return_value=(
                    result_receipt, self.program, self.staged.successor, self.program)) as owner:
            result = self.adopt()
        self.assertEqual(result, (self.parameters, self.optimizer, self.graph,
                                  result_receipt, self.program))
        self.assertIs(owner.call_args.kwargs["compiled_successor"], self.staged.successor)
        self.assertEqual((self.parameters, self.optimizer.state, self.receipt), before)
        self.optimizer.update.assert_not_called()
        self.assertEqual(tuple(self.root.iterdir()), ())

    def test_graph_growth_routes_the_exact_sealed_successor_without_compiling(self):
        graph = {**self.graph, "tokens": [*self.graph["tokens"], "fixture.extra"]}
        staged = self.stage(graph=graph)
        expected = (self.parameters, self.optimizer, graph, {"prepared": True}, self.program)
        with self.admitted_boundary(), patch(
                "bilqis_mlx.factory.candidate_realizations.admitted_candidate_graph",
                return_value=graph), patch.object(release_adoption,
                "_adopt_catalog_profile", return_value=expected) as owner:
            self.assertEqual(self.adopt(staged), expected)
        self.assertIs(owner.call_args.kwargs["compiled_successor"], staged.successor)
        self.assertIs(owner.call_args.args[7], self.optimizer)
        self.optimizer.update.assert_not_called()

    def test_changed_admitted_predecessor_cannot_substitute_a_new_successor(self):
        from bilqis_mlx.factory.executable_release import compile_executable_factory_release
        fixture = self.fixture.fixture
        changed = compile_executable_factory_release(
            self.current.curriculum, self.current.source_bindings, self.current.profile,
            fixture.registry, fixture.answers, source_root=None, graph=self.graph,
            verification_seed=97)
        with self.admitted_boundary(), patch.object(release_adoption._runtime_admission,
                "_require_executable_factory_admission", return_value=changed), \
                patch.object(release_adoption, "_adopt_executable_profile") as owner:
            with self.assertRaisesRegex(ValueError, "PREDECESSOR_DRIFT"):
                self.adopt()
            owner.assert_not_called()
        self.optimizer.update.assert_not_called()

    def test_jit_revalidates_before_entering_the_prepared_transaction(self):
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        proposal = propose_curriculum_delta(
            self.frontier, self.current, ledger, plan,
            self.checkpoint.sha256, self.checkpoint.optimizer_step,
            candidate_bindings=(self.staged.binding,))
        session = SimpleNamespace(resolve_ready_proposal=Mock(side_effect=lambda cp, prop:
            resolve_ready_candidate(self.frontier, self.current, ledger, plan,
                                    cp, prop, (self.staged,))))
        expected = (self.parameters, self.optimizer, self.graph, self.receipt, self.program)
        before = deepcopy((self.parameters, self.optimizer.state, self.receipt))
        with self.admitted_boundary(), patch.object(release_adoption._source_adapters_school,
                "live_source_registry", return_value=self.fixture.fixture.registry), \
                patch.object(release_adoption._factory_live_answers, "live_answer_registry",
                             return_value=self.fixture.fixture.answers), \
                patch.object(release_adoption, "_adopt_prepared_successor",
                             return_value=expected) as entry:
            result = release_adoption._adopt_jit_proposal(
                None, self.root, self.receipt, None, None, self.graph,
                self.parameters, self.optimizer, session, proposal, reserve_gib=100.)
        self.assertEqual(result, expected)
        session.resolve_ready_proposal.assert_called_once_with(self.checkpoint, proposal)
        self.assertIs(entry.call_args.args[8], self.staged)
        self.assertEqual((self.parameters, self.optimizer.state, self.receipt), before)
        self.optimizer.update.assert_not_called()
        self.assertEqual(ledger.receipts, ())
