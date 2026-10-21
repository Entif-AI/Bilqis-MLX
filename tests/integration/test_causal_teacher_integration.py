"""Source-bound disposable Grade C learning trial, parent ownership unchanged."""
from contextlib import redirect_stdout
import io
import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx import trainer as storage
from bilqis_mlx.compatibility.live_releases import initial_course
from bilqis_mlx.factory.generation import draw_executable_release_rows
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.learning.learning_experiment import Settings, select_source_lesson
from bilqis_mlx.source_adapters.school import live_source_registry
from tests.system import test_grade_c_trainer as fixtures
from tests.integration import test_numeric_staircase as staircase_fixtures


class CausalTeacherIntegrationTests(unittest.TestCase):
    def test_perfect_target_preflight_keeps_pending_provisionals_without_training(self):
        import mlx.core as mx

        previous = {"event": "PREVIOUS_PENDING_VISIT", "optimizer_step": 1}
        self.receipt["_pending_visit_events"] = [previous]
        original_bytes = (self.fixture.root / "state.json").read_bytes()
        original_step = int(self.fixture.optimizer.state["step"].item())
        original_lr = float(self.fixture.optimizer.learning_rate)

        def correctly_predict(_mx, _params, rows, _config, _ids):
            return {row["id"]: row["gold"] for row in rows}

        with patch.object(storage, "_predictions", side_effect=correctly_predict), \
                patch.object(storage, "_train_step", side_effect=AssertionError(
                    "PERFECT_TARGET_MUST_NOT_OPTIMIZE")), \
                patch.object(storage, "_persist", side_effect=AssertionError(
                    "PENDING_STUDENT_MUST_NOT_PERSIST")):
            updated = self.visit()

        mx.eval(self.fixture.optimizer.state)
        self.assertEqual(int(self.fixture.optimizer.state["step"].item()), original_step)
        self.assertEqual(float(self.fixture.optimizer.learning_rate), original_lr)
        self.assertEqual((self.fixture.root / "state.json").read_bytes(), original_bytes)
        self.assertEqual(updated["_pending_visit_events"][0], previous)
        skipped = updated["_pending_visit_events"][1]
        self.assertEqual(skipped["event"], "SCHOOL_PERFECT_TARGET_VISIT_SKIPPED")
        self.assertEqual(skipped["retained_optimizer_updates"], 0)
        self.assertEqual(updated["school"]["current_student"],
                         self.receipt["school"]["current_student"])

    @classmethod
    def setUpClass(cls):
        if not fixtures.PARENT.is_file():
            source = Path.home() / "Code/bilqis-mlx-retention-lab/vendor/legacy-v16"
            parent = (source / "runs/primitive-consolidation-v16-triplets" /
                      fixtures.PARENT.name)
            if not parent.is_file():
                raise FileNotFoundError(
                    "CAUSAL_TEACHER_PINNED_PARENT_FIXTURE_MISSING:" + str(parent))
            fixtures.SOURCE = source
            fixtures.PARENT = parent
        staircase_fixtures.NumericStaircaseTests.setUpClass()
        cls.source_root = fixtures.SOURCE
        cls.grade_a_course = initial_course(
            accepted_grade_a(fixtures.GradeCTrainerTests.manifest))

    def setUp(self):
        self.fixture=staircase_fixtures.NumericStaircaseTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.mx = self.fixture.mx
        self.course, self.receipt = self.fixture.start()
        with redirect_stdout(io.StringIO()):
            self.receipt, self.executable_release, self.schedule_program = (
                storage._ensure_executable_release(
                    self.fixture.root, self.receipt, self.course,
                    self.grade_a_course, self.source_root, self.fixture.graph))
            school = storage._state_from_json(
                self.receipt["school"], self.schedule_program)
            current_rubric = self.schedule_program.grades[-1].assessment_sha256
            if self.receipt.get("live_rubric_sha256") != current_rubric:
                self.receipt = storage._advance(
                    self.fixture.root,
                    {**self.receipt, "live_rubric_sha256": current_rubric},
                    school)
            self.receipt = storage._migrate_championship_governance(
                self.fixture.root, self.receipt, self.course)

    def visit(self):
        return storage._take_visit(
            self.mx,self.fixture.root,self.receipt,self.fixture.fixture.manifest,
            self.course,self.fixture.fixture.engine,
            self.fixture.params,self.fixture.optimizer,self.fixture.graph,
            steps_per_visit=1,batch_size=6,reserve_gib=0.,
            source_root=self.source_root,
            learning_settings=Settings(probe_each=6,mature_max_loss=2,
                                       introduction_extra_loss=2))

    def resume(self):
        return storage._resume(
            self.fixture.root, self.fixture.fixture.manifest, self.course,
            self.fixture.fixture.policy_sha,
            grade_a_course=self.grade_a_course, source_root=self.source_root,
            admitted_courses={self.course.version: self.course})

    def test_tighter_policy_resume_is_metadata_only_and_durable(self):
        school = storage._state_from_json(
            self.receipt["school"], self.schedule_program)
        old = asdict(Settings(mature_max_loss=2))
        previous = storage._advance(self.fixture.root,
            {**self.receipt, "learning_experiment": {
                "version": storage.LEARNING_EXPERIMENT_VERSION, "settings": old}},
            school, persist=False)
        previous = storage._persist(self.fixture.root, storage._with_delivery_outbox(
            previous, ({"event": "FIXTURE_PREVIOUS_POLICY",
                        "generation": previous["generation"]},)))
        student = dict(previous["school"]["current_student"])
        updated = storage._reconcile_learning_settings(
            self.fixture.root, previous, self.course, Settings(), self.fixture.optimizer)
        self.assertEqual(updated["generation"], previous["generation"] + 1)
        self.assertEqual(updated["school"]["current_student"], student)
        self.assertEqual(updated["learning_experiment"]["settings"]["mature_max_loss"], 1)
        self.assertEqual(updated["learning_policy_revisions"][0]["from"], old)
        self.assertEqual(storage._reconcile_learning_settings(
            self.fixture.root, updated, self.course, Settings(), self.fixture.optimizer), updated)
        with self.assertRaisesRegex(ValueError, "IDENTICAL_OPT_IN"):
            storage._reconcile_learning_settings(
                self.fixture.root, updated, self.course,
                Settings(mature_max_loss=2), self.fixture.optimizer)
        with redirect_stdout(io.StringIO()):
            _, own, _, reloaded = self.resume()
        self.assertEqual(reloaded, updated)
        self.assertEqual(int(own.state["step"].item()), student["optimizer_step"])

    def test_existing_exam_peak_is_seeded_before_any_new_training(self):
        school = storage._state_from_json(
            self.receipt["school"], self.schedule_program)
        pointer = dict(self.receipt["school"]["current_student"])
        prior = {"student_sha256": pointer["sha256"],
                 "optimizer_step": pointer["optimizer_step"],
                 "exam_rubric_sha256": "rubric", "cohort_sha256": "cohort",
                 "assessment_scope_sha256": "scope",
                 "scores": {"A.EDGE": {"correct": 11, "total": 12}}}
        saved = storage._advance(self.fixture.root, self.receipt, school,
                                 last_exam=prior, persist=True)
        seeded = storage._seed_saved_whole_student_peak(
            self.fixture.root, saved, self.course, self.fixture.optimizer)
        self.assertEqual(seeded["generation"], saved["generation"] + 1)
        self.assertEqual(seeded["school"]["current_student"], pointer)
        self.assertEqual(seeded["whole_student_peaks"][0]["checkpoint"], pointer)
        self.assertEqual(storage._seed_saved_whole_student_peak(
            self.fixture.root, seeded, self.course, self.fixture.optimizer), seeded)
        storage._verify_best_custody(self.fixture.root, seeded)
        self.assertEqual(json.loads((self.fixture.root / "state.json").read_text()), seeded)

    def test_retention_peak_is_protected_at_retirement_boundary(self):
        pointer = dict(self.receipt["school"]["current_student"])
        protected = {**self.receipt, "whole_student_peaks": [{
            "schema": "bilqis.mlx.whole-student-retention/v1",
            "checkpoint": pointer, "scope_sha256": "fixture"}]}
        storage._verify_best_custody(self.fixture.root, protected)
        with patch.object(storage, "retire_bundles", return_value=()) as retired:
            storage._publish_boundary(self.fixture.root, protected, (), ())
        self.assertIn(pointer["filename"], retired.call_args.args[1])

    def test_experimental_operator_refuses_active_or_external_run_dir_before_gpu(self):
        # operate is never entered by tests: this must fail at its first
        # read-only pathname guard, before source loading or optimizer setup.
        from unittest.mock import patch
        with patch.object(storage, "prepare_source",
                          side_effect=AssertionError("SOURCE_SHOULD_NOT_BE_LOADED")):
            with self.assertRaisesRegex(
                    ValueError, "LEARNING_EXPERIMENT_REQUIRES_ISOLATED_WORKTREE_RUN"):
                storage.operate(
                    self.fixture.root, fixtures.SOURCE, fixtures.PARENT,
                    self.fixture.fixture.manifest, retention_enabled=True)

    def test_first_staircase_visit_stop_and_resume_persists_context_and_own_adamw(self):
        # Regression for a pre-existing ff64 bug: before its first Grade C
        # exam, last_exam is legitimately None. A human stop must still
        # publish the complete live model/optimizer and candidate receipts.
        with redirect_stdout(io.StringIO()):
            changed=self.visit()
            saved=storage._flush_working_student(
                self.mx,self.fixture.root,changed,self.fixture.fixture.manifest,
                self.course,self.fixture.params,self.fixture.optimizer,
                self.fixture.graph,reserve_gib=0.,source_root=self.source_root)
            parameters,own_adamw,graph,reloaded=self.resume()
        self.assertEqual(saved,reloaded)
        self.assertEqual(reloaded["teacher"]["causal_experiment"]["events"],1)
        self.assertEqual(reloaded["learning_experiment"]["version"],
                         "bilqis.mlx.causal-teacher-experiment/v1")
        self.assertEqual(int(own_adamw.state["step"].item()),
                         int(self.fixture.optimizer.state["step"].item()))
        self.assertEqual(set(parameters),set(self.fixture.params))
        self.assertEqual(graph,self.fixture.graph)

    def test_old_model_metadata_222_never_overrides_expanded_graph_vocabulary(self):
        from bilqis_mlx.semantics.abi import HISTORICAL_PREFIX_SIZE
        actual=len(self.fixture.graph["tokens"])
        self.assertGreater(actual,HISTORICAL_PREFIX_SIZE)
        # Deliberately reconstruct a historical pre-fix *receipt* in a
        # disposable run. New numeric admissions already set the live size.
        school=storage._state_from_json(
            self.receipt["school"],self.schedule_program)
        stale=storage._advance(
            self.fixture.root,
            {**self.receipt,"config":{**self.receipt["config"],
                         "vocab_size":HISTORICAL_PREFIX_SIZE}},
            school,persist=False)
        stale=storage._persist(self.fixture.root,storage._with_delivery_outbox(
            stale,({"event":"SYNTHETIC_STALE_VOCAB_STATE",
                    "generation":stale["generation"]},)))
        self.assertEqual(stale["config"]["vocab_size"],HISTORICAL_PREFIX_SIZE)
        before=(self.receipt["school"]["current_student"],
                int(self.fixture.optimizer.state["step"].item()))
        with redirect_stdout(io.StringIO()):
            corrected=storage._reconcile_vocabulary_metadata(
                self.fixture.root,stale,self.course,self.fixture.params,
                self.fixture.optimizer,self.fixture.graph)
            _,own,_,reloaded=self.resume()
        self.assertEqual(corrected,reloaded)
        self.assertEqual(corrected["config"]["vocab_size"],actual)
        self.assertEqual(corrected["school"]["current_student"],before[0])
        self.assertEqual(int(own.state["step"].item()),before[1])
        self.assertEqual(corrected["generation"],stale["generation"]+1)
        self.assertEqual(json.loads((self.fixture.root/"states"/
                          f"{stale['generation']:07d}.json").read_text())[
                          "config"]["vocab_size"],HISTORICAL_PREFIX_SIZE)
        self.assertEqual(storage._reconcile_vocabulary_metadata(
            self.fixture.root,corrected,self.course,self.fixture.params,
            self.fixture.optimizer,self.fixture.graph),corrected)

    def test_provisional_grade_c_candidate_has_context_and_real_old_rows(self):
        school = storage._state_from_json(
            self.receipt["school"],self.schedule_program)
        with patch.object(storage,"decide_learning_trial",
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
        with patch.object(storage,"_draw_live_rows",side_effect=capture):
            rows,protected,_ = storage._learning_probe_rows(
                self.source_root,self.fixture.graph,latest,self.course,school,
                "C.COUNT",Settings(),schedule_program=self.schedule_program,
                executable_release=self.executable_release)
        self.assertEqual(requested["C.COUNT"],21)
        self.assertTrue(protected)
        self.assertTrue(all(requested[cap]==6 for cap in protected))
        self.assertEqual(Counter(row["capability"] for row in rows)["C.COUNT"],21)

    def test_rejected_candidate_keeps_parent_and_adamw_byte_identical(self):
        baseline={name:np.asarray(value).copy()
                  for name,value in self.fixture.params.items()}
        moments={name:{k:np.asarray(v).copy() for k,v in cell.items()}
                 for name,cell in self.fixture.optimizer.state.items()
                 if isinstance(cell,dict)}
        before_step=int(self.fixture.optimizer.state["step"].item())
        real_decider=storage.decide_learning_trial

        def forced_rejection(*args,**kwargs):
            decision=real_decider(*args,**kwargs)
            # Test the transaction path, not invented regression evidence.
            return {**decision,"decision":"REJECT",
                    "reason":"FIXTURE_FORCED_TRANSACTION_REJECTION"}

        with patch.object(storage,"decide_learning_trial",
                          side_effect=forced_rejection),redirect_stdout(io.StringIO()):
            result=self.visit()
        event=result["_pending_visit_events"][-1]
        self.assertEqual(event["candidate_retention"]["decision"],"REJECT")
        self.assertEqual(event["retained_optimizer_updates"],0)
        self.assertEqual(event["teacher_reward"],0.)
        self.assertEqual(int(self.fixture.optimizer.state["step"].item()),before_step)
        self.assertLess(event["context_teacher_credit"]["teacher_context_reward"],0)
        for name,value in baseline.items():
            np.testing.assert_array_equal(np.asarray(self.fixture.params[name]),value)
            for kind,original in moments[name].items():
                np.testing.assert_array_equal(
                    np.asarray(self.fixture.optimizer.state[name][kind]),original)
        self.assertGreater(result["teacher"]["causal_experiment"]["events"],0)

    def test_typed_actions_have_actual_distinct_effect_on_selected_source_rows(self):
        registry = live_source_registry()
        raw = draw_executable_release_rows(
            self.source_root, self.fixture.graph, self.executable_release,
            registry, capability="C.COUNT", legacy_course=self.course,
            each=12, seed=109)
        prior = draw_executable_release_rows(
            self.source_root, self.fixture.graph, self.executable_release,
            registry, capability="A.IDENTITY", legacy_course=self.course,
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


if __name__=="__main__":
    unittest.main()
