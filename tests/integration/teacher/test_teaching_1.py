"""Teacher integration contracts; original evidence and boundaries preserved."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bilqis_mlx import trainer as storage
from bilqis_mlx.factory.generation import draw_executable_release_rows
from bilqis_mlx.learning.learning_experiment import Settings, select_source_lesson
from bilqis_mlx.source_adapters.school import live_source_registry
from tests.system import test_grade_c_trainer as fixtures
from tests.integration.teacher.fixtures import TeacherFixture


class TeachingTests(TeacherFixture, unittest.TestCase):
    def test_registered_issue_custody_reaches_source_guard_from_external_checkout(self):
        from bilqis_mlx.runtime.experiment_runs import ExperimentRunBudget
        with tempfile.TemporaryDirectory() as directory:
            owner = ExperimentRunBudget(Path(directory) / "issue349")
            run = owner.create("primary")
            with patch('bilqis_mlx.runtime.session.prepare_source', side_effect=RuntimeError(
                    "SOURCE_BOUNDARY_REACHED")):
                with self.assertRaisesRegex(RuntimeError, "SOURCE_BOUNDARY_REACHED"):
                    storage.operate(
                        run, fixtures.SOURCE, fixtures.PARENT,
                        self.fixture.fixture.manifest, experiment_budget=owner)
            self.assertEqual({p.name for p in run.iterdir()}, {".experiment-run.json"})

    def test_provisional_grade_c_candidate_has_context_and_real_old_rows(self):
        school = storage._state_from_json(
            self.receipt["school"],self.schedule_program)
        with patch('bilqis_mlx.learning.learning_experiment.decide',
                          wraps=storage.decide_learning_trial) as gate,redirect_stdout(io.StringIO()):
            result=self.visit()
        self.assertEqual(gate.call_args.kwargs["mature_grades"],frozenset(school.champions))
        event=result["_pending_visit_events"][-1]
        outcome=event["candidate_retention"]
        # A real source-scored disposable update is promoted only on strictly
        # positive target-probe gain; the exact outcome is model-dependent.
        if outcome["decision"]=="PROVISIONAL":
            self.assertGreater(outcome["local_correct_delta"],0)
            self.assertEqual(event["retained_optimizer_updates"],1)
        else:
            self.assertEqual(outcome["decision"],"REJECT")
            self.assertTrue(outcome["local_correct_delta"]<=0 or outcome["exceeded"])
            self.assertEqual(event["retained_optimizer_updates"],0)
        self.assertEqual(event["candidate_attempt_optimizer_step"],2)
        self.assertEqual(int(self.fixture.optimizer.state["step"].item()),
                         1+event["retained_optimizer_updates"])
        self.assertEqual(result["teacher"]["causal_experiment"]["events"],1)
        self.assertEqual(result["learning_experiment"]["settings"]["probe_each"],6)
        self.assertEqual(event["typed_policy_controls"]["optimizer_batches_observed"],1)
        self.assertGreaterEqual(event["typed_policy_controls"]["old_grade_examples_delivered"],1)
        monitored=set(event["candidate_retention"]["deltas"])
        eligible=set(storage.assessment_capabilities(
                self.schedule_program,
                storage._state_from_json(
                    self.receipt["school"],self.schedule_program))) | {"C.COUNT"}
        self.assertTrue(monitored <= eligible)
        self.assertIn("C.COUNT",monitored)
        self.assertLessEqual(len(monitored),9)
        self.assertEqual(outcome["active_probe_total"],12)
        self.assertEqual(outcome["local_correct_delta"],
                         outcome["active_probe_after"]-outcome["active_probe_before"])
        if outcome["qualification_stage"] == "TARGET_ONLY_REJECTED":
            self.assertEqual(monitored, {"C.COUNT"})
            self.assertEqual(outcome["decision"], "REJECT")
            self.assertEqual(outcome["fixed_grade_replay"]["status"], "NOT_MEASURED")
            self.assertLessEqual(outcome["local_correct_delta"], 0)
        else:
            self.assertIn(outcome["qualification_stage"],
                          ("COMPLETE_SAME_GRADE", "GRADE_NET_REJECTED"))
            self.assertTrue(any(k.startswith("A.") for k in monitored))
            self.assertTrue(any(k.startswith("B.") for k in monitored))
        self.assertEqual(len(eligible)-len(monitored),
                         event["candidate_retention"]["unsampled_admitted_capabilities"])

    def test_protected_probes_remain_bounded_while_target_matches_exam_size(self):
        from collections import Counter
        from unittest.mock import patch
        source = storage._draw_live_rows
        requested = {}
        school = storage._state_from_json(
            self.receipt["school"],self.schedule_program)
        scores = {"C.COUNT": {"correct": 19, "total": 21}}
        latest = {**self.receipt, "last_exam": {"scores": scores}}
        def capture(*args,**kwargs):
            requested[kwargs["capability"]]=kwargs["each"]
            return source(*args,**kwargs)
        with patch('bilqis_mlx.runtime.assessment._draw_live_rows',side_effect=capture):
            rows,protected,_ = storage._learning_probe_rows(
                self.source_root,self.fixture.graph,latest,self.course,school,
                "C.COUNT",Settings(),schedule_program=self.schedule_program,
                executable_release=self.executable_release)
        self.assertEqual(requested["C.COUNT"],21)
        self.assertTrue(protected)
        self.assertTrue(all(requested[cap]==6 for cap in protected))
        self.assertEqual(Counter(row["capability"] for row in rows)["C.COUNT"],21)

    def test_typed_actions_have_actual_distinct_effect_on_selected_source_rows(self):
        registry = live_source_registry()
        raw = draw_executable_release_rows(
            self.source_root, self.fixture.graph, self.executable_release,
            registry, capability="C.COUNT",
            each=12, seed=109)
        prior = draw_executable_release_rows(
            self.source_root, self.fixture.graph, self.executable_release,
            registry, capability="A.IDENTITY",
            each=12, seed=29)
        x,trace1=select_source_lesson(raw,prior,
            {"old":0,"contrast":0,"depth":1},seed=13,batch_size=6)
        y,trace2=select_source_lesson(raw,prior,
            {"old":20,"contrast":1,"depth":3},seed=13,batch_size=6)
        self.assertEqual(trace1["effective_old_grade_examples"],0)
        self.assertGreater(trace2["effective_old_grade_examples"],0)
        self.assertEqual({r["capability"] for r in x},{"C.COUNT"})
        self.assertIn("A.IDENTITY",{r["capability"] for r in y})
        self.assertNotEqual([r["id"] for r in x],[r["id"] for r in y])
        self.assertEqual(trace2["preview_control"],"NOT_AVAILABLE_UNADMITTED_FUTURE_GRADE")

    def test_binary_lesson_keeps_every_operand_truth_pattern_with_old_rehearsal(self):
        patterns=((False,False),(False,True),(True,False),(True,True))
        current=[]
        for bits in patterns:
            for index in range(8):
                current.append({
                    "id":f"current-{bits}-{index}",
                    "source_id":f"current-{bits}-{index}",
                    "capability":"B.IFF",
                    "gold":"TRUE" if bits[0]==bits[1] else "FALSE",
                    "operand_truths":list(bits),
                    "tokens":[1,2,3+index],
                })
        prior=[{
            "id":f"prior-{index}","source_id":f"prior-{index}",
            "capability":"A.IDENTITY",
            "gold":"TRUE" if index%2 else "FALSE","tokens":[1,2],
        } for index in range(32)]
        picked,trace=select_source_lesson(
            current,prior,
            {"old":20,"depth":3,"contrast":0.0,
             "distill":0.15,"lr":0.0003,"preview":4},
            seed=0,batch_size=32)
        target=[row for row in picked if row["capability"]=="B.IFF"]
        self.assertEqual({tuple(row["operand_truths"]) for row in target},set(patterns))
        self.assertGreaterEqual(len(target),len(patterns))
        self.assertEqual(trace["current_semantic_patterns_required"],4)
        self.assertEqual(trace["current_semantic_patterns_delivered"],4)
