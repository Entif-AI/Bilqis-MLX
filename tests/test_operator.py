"""Human root commands must not accidentally begin optimization."""
from contextlib import redirect_stdout,redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bilqis_mlx.cli import main,parse_args,DEFAULT_RUN,ORIGINAL_CHECKPOINT
from bilqis_mlx.spiral_dashboard import TABLES, Dashboard
from bilqis_mlx.grade_a_dashboard import build, ingest
from bilqis_mlx.school_telemetry import SchoolTelemetry


class OperatorTests(unittest.TestCase):
    def test_live_visit_projects_rows_once_before_durable_replay(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        board.state["attempted_steps"] = 0
        telemetry = SchoolTelemetry(board, active_grades=("B",))
        visit = {
            "event": "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED", "grade": "B",
            "generation": 42, "optimizer_step": 100,
            "capability": "B.OR",
            "source_training_accuracy_before": 0.5,
            "source_training_accuracy_after": 0.5,
            "teacher_reward": 0.0, "teacher_policy": "test",
            "strategy": {}, "loss": 0.1, "gradient_norm": 0.1,
            "attempted_optimizer_updates": 16,
            "retained_optimizer_updates": 16,
            "checkpoint_status": "PROVISIONAL_UNTIL_NEXT_RECOVERY_BOUNDARY",
            "next_phase": "RECOVERY_1",
        }
        telemetry.ingest({**visit, "_live_ephemeral": True,
                          "_dashboard_redraw": False})
        self.assertEqual(board.state["attempted_steps"], 16)
        self.assertEqual(board.state["retained_steps"], 16)
        self.assertEqual(board.state["retained_visits"], 1)
        self.assertEqual(telemetry.visits, 1)
        self.assertEqual(len(board.rows["CANDIDATES"]), 1)
        self.assertEqual(len(board.rows["SOUP & TEACHER"]), 1)

        durable = {**visit, "checkpoint_status": "RECORDED_AT_BOUNDARY"}
        telemetry.ingest(durable)
        self.assertEqual(board.state["attempted_steps"], 16)
        self.assertEqual(board.state["retained_steps"], 16)
        self.assertEqual(board.state["retained_visits"], 1)
        self.assertEqual(telemetry.visits, 1)
        self.assertEqual(len(board.rows["CANDIDATES"]), 1)
        self.assertEqual(len(board.rows["SOUP & TEACHER"]), 1)
        self.assertFalse(durable["_dashboard_redraw"])

    def test_boolean_association_visit_is_visible_in_candidate_and_system_text(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(board, active_grades=("A", "B", "C"))
        telemetry.ingest({
            "event": "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED",
            "grade": "B",
            "active_grade": "B",
            "generation": 43,
            "optimizer_step": 116,
            "capability": "B.IMPLIES",
            "retained_optimizer_updates": 0,
            "candidate_retention": {
                "decision": "REJECT",
                "reason": "NO_MEASURABLE_TARGET_GAIN",
            },
            "boolean_association_bridge": {
                "enabled": True,
                "active_for_visit": True,
                "borrowed_source_grades": ["A", "C"],
                "delivered_examples": 128,
            },
        })

        self.assertIn(
            "COMPOSE A+C->B x128",
            board.rows["CANDIDATES"][-1]["decision"],
        )
        compose = board.rows["SYSTEM & QUALIFICATION"][-1]
        self.assertEqual(compose["kind"], "COMPOSE")
        self.assertEqual(compose["grade"], "B")
        self.assertEqual(compose["detail"], "COMPOSE A+C->B x128 | B.IMPLIES")

    def test_live_exam_reports_actual_champion_title_movement_not_generic_saved_label(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(
            board, active_grades=("B",), champions={"B": {"sha256": "f" * 64}})
        telemetry.ingest({
            "event": "SCHOOL_LIVE_EXAM_COMMITTED",
            "grade": "B",
            "generation": 51,
            "optimizer_step": 232392,
            "student_sha256": "a" * 64,
            "rubric": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "d" * 64,
            "cohort_file": "cohorts/d.json",
            "generator_version": "test/live-v1",
            "phase": "RECOVERY_1",
            "scores": {"B.OR": {"correct": 9, "total": 12}},
            "championship_epoch": {
                "earned_roles": ["B.OR"],
                "active_role_count": 1,
                "active_soup_grades": ["B"],
            },
        })

        mastery = board.rows["GRADES & MASTERY"][-1]
        self.assertIn("TITLE MOVED 1", mastery["outcome"])
        self.assertNotIn("CHAMPION SAVED", mastery["outcome"])
        champion = board.rows["SYSTEM & QUALIFICATION"][-1]
        self.assertEqual(champion["kind"], "CHAMPION")
        self.assertEqual(champion["grade"], "B")
        self.assertIn("B.OR 9/12", champion["detail"])
        self.assertIn("step 232392", champion["detail"])

    def test_live_exam_with_existing_champion_but_no_title_change_says_so(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(
            board, active_grades=("B",), champions={"B": {"sha256": "f" * 64}})
        telemetry.ingest({
            "event": "SCHOOL_LIVE_EXAM_COMMITTED",
            "grade": "B",
            "generation": 52,
            "optimizer_step": 232392,
            "student_sha256": "a" * 64,
            "rubric": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "e" * 64,
            "cohort_file": "cohorts/e.json",
            "generator_version": "test/live-v1",
            "phase": "RECOVERY_1",
            "scores": {"B.OR": {"correct": 8, "total": 12}},
            "championship_epoch": {
                "earned_roles": [],
                "active_role_count": 1,
                "active_soup_grades": ["B"],
                "cross_origin_decisions": [{
                    "grade": "B",
                    "decision": "DENY_NO_STRICT_SCHOOL_VICTORY",
                }],
            },
        })

        mastery = board.rows["GRADES & MASTERY"][-1]
        self.assertIn("NO TITLE CHANGE", mastery["outcome"])
        self.assertNotIn("CHAMPION SAVED", mastery["outcome"])
        champion = board.rows["SYSTEM & QUALIFICATION"][-1]
        self.assertEqual(champion["kind"], "CHAMPION")
        self.assertIn("DENY_NO_STRICT_SCHOOL_VICTORY", champion["detail"])

    def test_flash_scheduler_exam_is_scope_bound_and_explicitly_non_title(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(board, active_grades=("A", "B", "C"))
        telemetry.ingest({
            "event": "SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED",
            "grade": "C",
            "generation": 53,
            "optimizer_step": 232472,
            "student_sha256": "a" * 64,
            "rubric": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "d" * 64,
            "cohort_file": "cohorts/d.json",
            "generator_version": "test/live-v1",
            "phase": "RECOVERY_1",
            "flash_scheduler_only": True,
            "scores": {
                "A.IDENTITY": {"correct": 12, "total": 12},
                "B.OR": {"correct": 8, "total": 12},
                "C.ADD": {"correct": 20, "total": 21},
            },
            "championship_epoch": {
                "earned_roles": [], "active_role_count": 19,
                "active_soup_grades": ["A", "B", "C"],
                "cross_origin_decisions": [],
            },
        })

        rows = list(board.rows["GRADES & MASTERY"])[-3:]
        self.assertTrue(all("FLASH SAMPLE" in row["outcome"] for row in rows))
        self.assertTrue(all("NO TITLES" in row["outcome"] for row in rows))
        self.assertTrue(all(key[2] == "c" * 64 for key in telemetry.latest))

    def test_dashboard_top_right_shows_step_rate_and_all_grade_accuracy(self):
        now = [100.0]
        board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                          clock=lambda: now[0])
        board.state.update(step=100, attempted_steps=0, retained_visits=1, visits=12)
        board.rows["GRADES & MASTERY"].extend([
            {"grade": "A", "latest": "71/72", "right_pct": "98.6%"},
            {"grade": "B", "latest": "47/72", "right_pct": "65.3%"},
            {"grade": "C", "latest": "137/147", "right_pct": "93.2%"},
        ])

        board.draw()
        board.state.update(attempted_steps=48, _rate_sample_eligible=False)
        now[0] = 101.0
        board.draw()  # Buffered boundary replay must not fake throughput.
        board.state["_rate_sample_eligible"] = True
        now[0] = 102.0
        board.draw()
        shown = board.render(width=150, height=38)

        self.assertIn("1,440 attempted steps/min (1 retained)", shown.splitlines()[0])
        self.assertIn("ALL 255/291 = 87.6% correct (last measured)", shown.splitlines()[1])

    def test_resume_instructions_are_flag_free_at_default_retention_policy(self):
        from bilqis_mlx.grade_a_trainer import _resume_command
        from bilqis_mlx.learning_experiment import Settings
        from bilqis_mlx.paths import LEGACY_SOURCE, active_run_dir

        self.assertEqual(_resume_command(active_run_dir(), LEGACY_SOURCE, Settings()),
                         "npm run train -- --human-run --resume")
        stricter = _resume_command(active_run_dir(), LEGACY_SOURCE,
                                   Settings(mature_max_loss=0))
        self.assertIn("--retention-mature-max-loss 0", stricter)
        self.assertNotIn("--experimental-retention", stricter)
        with tempfile.TemporaryDirectory() as tmp:
            unprotected = _resume_command(Path(tmp), LEGACY_SOURCE, None)
            self.assertIn("--no-retention", unprotected)
            self.assertIn("--run-dir", unprotected)

        bridged = _resume_command(
            active_run_dir(), LEGACY_SOURCE, Settings(),
            boolean_association_bridge=True)
        self.assertIn("--boolean-association-bridge", bridged)
        serial = _resume_command(
            active_run_dir(), LEGACY_SOURCE, Settings(), source_prefetch_workers=0)
        self.assertIn("--source-prefetch-workers 0", serial)
        one_worker = _resume_command(
            active_run_dir(), LEGACY_SOURCE, Settings(), source_prefetch_workers=1)
        self.assertIn("--source-prefetch-workers 1", one_worker)

    def test_retention_defaults_on_and_explicit_independent_opt_out(self):
        self.assertFalse(parse_args(["train", "--resume"]).no_retention)
        self.assertTrue(parse_args([
            "train", "--resume", "--boolean-association-bridge"]
        ).boolean_association_bridge)
        grace = parse_args([
            "train", "--resume", "--stagnation-grace-grade", "B",
            "--stagnation-grace-steps", "100000"])
        self.assertEqual(grace.stagnation_grace_grade, "B")
        self.assertEqual(grace.stagnation_grace_steps, 100000)
        with tempfile.TemporaryDirectory() as tmp:
            out=io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train", "--dry-run", "--run-dir", tmp]), 0)
            self.assertEqual(json.loads(out.getvalue())["retention_mode"], "DEFAULT_PROTECTED")
            out=io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train", "--dry-run", "--no-retention",
                                       "--run-dir", tmp]), 0)
            self.assertEqual(json.loads(out.getvalue())["retention_mode"], "EXPLICIT_UNPROTECTED")
            out=io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train", "--dry-run", "--experimental-retention",
                                       "--run-dir", tmp]), 0)
            self.assertEqual(json.loads(out.getvalue())["retention_mode"], "DEFAULT_PROTECTED")
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parse_args(["train", "--experimental-retention", "--no-retention"])

    def test_no_retention_cannot_target_default_run_or_protected_history(self):
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main(["train", "--dry-run", "--no-retention"]), 2)
        self.assertIn("NO_RETENTION_REQUIRES_INDEPENDENT_RUN_DIR", errors.getvalue())
        with tempfile.TemporaryDirectory() as tmp:
            saved={"learning_experiment":{"version":"existing-protected-policy"}}
            path=Path(tmp)/"state.json"
            original=json.dumps(saved).encode()
            path.write_bytes(original)
            with redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(main(["train", "--dry-run", "--resume",
                                       "--no-retention", "--run-dir", tmp]), 2)
            self.assertIn("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN",
                          errors.getvalue())
            self.assertEqual(path.read_bytes(),original)

    def test_direct_operator_refuses_protected_opt_out_before_source_or_gpu(self):
        from bilqis_mlx import grade_a_trainer as trainer

        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state=root/"state.json"
            payload=json.dumps({"learning_experiment":{"version":"protected"}}).encode()
            state.write_bytes(payload)
            with patch.object(trainer, "prepare_source", side_effect=AssertionError(
                    "NO_SOURCE_OR_GPU_BEFORE_POLICY_REFUSAL")):
                with self.assertRaisesRegex(
                        ValueError, "LEARNING_EXPERIMENT_PROTECTED_RESUME_REQUIRES_RETENTION"):
                    trainer.operate(root, root, root, root, resume=True,
                                    retention_enabled=False)
            self.assertEqual(state.read_bytes(),payload)

    def test_human_operator_receives_default_protected_mode_without_opt_in(self):
        from bilqis_mlx import grade_a_trainer as trainer
        no_neural_work = "TEST_BLOCKS_ANY_NEURAL_WORK"
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(trainer, "operate", side_effect=ValueError(
                    no_neural_work)) as operate, \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train", "--human-run", "--resume",
                                       "--run-dir", tmp]), 2)
            self.assertTrue(operate.call_args.kwargs["retention_enabled"])
            self.assertEqual(operate.call_args.kwargs["source_prefetch_workers"], 2)
            with patch.object(trainer, "operate", side_effect=ValueError(
                    no_neural_work)) as operate, \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train", "--human-run", "--resume",
                                       "--source-prefetch-workers", "0",
                                       "--run-dir", tmp]), 2)
            self.assertEqual(operate.call_args.kwargs["source_prefetch_workers"], 0)
            with patch.object(trainer, "operate", side_effect=ValueError(
                    no_neural_work)) as operate, \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train", "--human-run", "--no-retention",
                                       "--run-dir", tmp]), 2)
            self.assertFalse(operate.call_args.kwargs["retention_enabled"])

    def test_human_operator_passes_flash_mode_without_changing_retention(self):
        from bilqis_mlx import grade_a_trainer as trainer
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                trainer, "operate", side_effect=ValueError(
                    "FLASH_TEST_NO_NEURAL_TRAINING")) as operate, \
                redirect_stderr(io.StringIO()):
            self.assertEqual(main([
                "train", "--human-run", "--resume", "--flash-mode",
                "--run-dir", tmp]), 2)
        self.assertTrue(operate.call_args.kwargs["flash_mode"])
        self.assertTrue(operate.call_args.kwargs["retention_enabled"])

    def test_worktree_preflight_uses_explicit_source_paths_without_global_mutation(self):
        from bilqis_mlx import cli
        original = cli.LEGACY_ROOT, cli.ORIGINAL_CHECKPOINT
        with tempfile.TemporaryDirectory() as tmp:
            donor = Path(tmp) / "explicit-donor"
            out = io.StringIO()
            with patch("bilqis_mlx.grade_a_manifest.verify_manifest", return_value={
                    "verified_items": 216, "exam_rubric_sha256": "a" * 64}) as verify, \
                    patch("bilqis_mlx.cli.assert_headroom", return_value={}), redirect_stdout(out):
                self.assertEqual(main(["train", "--dry-run", "--verify-source", "--run-dir", tmp,
                                       "--legacy-code-root", str(donor)]), 0)
            self.assertEqual(verify.call_args.args[1], donor)
            self.assertEqual(verify.call_args.args[2], donor / "runs" / "primitive-consolidation-v16-triplets" /
                             ORIGINAL_CHECKPOINT.name)
            self.assertEqual((cli.LEGACY_ROOT, cli.ORIGINAL_CHECKPOINT), original)
            self.assertFalse(json.loads(out.getvalue())["neural_training_started_by_this_command"])

    def test_grade_c_preflight_reports_missing_approved_registry_as_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            saved = {
                "schema": "bilqis.mlx.human-grade-a-trainer/v1",
                "generation": 3, "result": "GRADE_B_MASTERED_AWAITING_GRADE_C",
                "school": {"active_grades": ["A", "B"], "grade_index": 1,
                           "stage": "AWAITING_NEXT_GRADE", "visits": 4,
                           "current_student": {"sha256": "a" * 64,
                                               "optimizer_step": 204072},
                           "champions": {"A": {}, "B": {}}},
                "teacher": {"events": 10, "strategies": {}}, "last_exam": None,
            }
            (run / "state.json").write_text(json.dumps(saved))
            out = io.StringIO()
            with patch("bilqis_mlx.live_grade_c.REGISTRY_PATH", run / "missing.json"), \
                    patch("bilqis_mlx.grade_c_preflight.qualify",
                          side_effect=AssertionError("unverified C must not qualify")), \
                    patch("bilqis_mlx.cli.assert_headroom", return_value={}), \
                    redirect_stdout(out):
                self.assertEqual(main(["train", "--dry-run", "--resume",
                                       "--run-dir", tmp]), 0)
            report = json.loads(out.getvalue())
            self.assertEqual(report["next_grade"], "C")
            self.assertEqual(report["blockers"], [
                "GRADE_C_NATIVE_REGISTRY_ARTIFACT_MISSING"])
            self.assertNotIn("next_grade_selection_review", report)
            self.assertNotIn("next_grade_source", report)
            self.assertTrue((run / "state.json").is_file())

    def test_resume_terminal_clears_previous_session_stop_before_training(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True

        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            event = {"event": "SCHOOL_SESSION_STOPPED", "grade": "B",
                     "stop_reason": "TIME_LIMIT_REACHED", "generation": 6809,
                     "optimizer_step": 203880, "visits_this_command": 1599,
                     "elapsed_seconds": 5409.7}
            original = json.dumps(event) + "\n"
            (run / "events.jsonl").write_text(original)
            old_view = build(run, stream=io.StringIO())
            self.assertEqual(old_view.state["stop"], "TIME_LIMIT_REACHED")

            terminal = Terminal()
            with patch("bilqis_mlx.cli.sys.stdout", terminal), patch(
                    "bilqis_mlx.grade_a_trainer.operate",
                    side_effect=ValueError("DISPOSABLE_TEST_NO_NEURAL_TRAINING")), \
                    redirect_stderr(io.StringIO()):
                result = main(["train", "--human-run", "--resume",
                               "--minutes", "90", "--run-dir", tmp])
            self.assertEqual(result, 2)  # Stub prevents any training call.
            self.assertIn("RESUMING", terminal.getvalue())
            self.assertNotIn("TIME_LIMIT_REACHED", terminal.getvalue())
            self.assertEqual((run / "events.jsonl").read_text(), original)
            # Historical dashboard continues to report the actual old stop.
            self.assertEqual(build(run, stream=io.StringIO()).state["stop"],
                             "TIME_LIMIT_REACHED")

    def test_saved_grade_a_dashboard_replays_exam_without_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "events.jsonl").write_text(json.dumps({
                "event": "GRADE_A_EXAM_COMMITTED", "generation": 8,
                "phase": "RECOVERY_1", "rubric": "fixture-grade-a-rubric",
                "student_sha256": "fixture-intact-model", "scores": {
                    name: {"correct": 6, "total": 12}
                    for name in ("A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS")
                }}) + "\n")
            board = build(run, stream=io.StringIO())
            output = board.render(width=115, height=38)
            self.assertIn("SEALED EXAM 36/72", output)
            self.assertIn("50.0%", output)
            self.assertIn("RECOVERY_1", output)
            self.assertFalse((run / "state.json").exists())

    def test_event_ingest_updates_live_view_without_running_optimizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "GRADE_A_TEACHER_VISIT_COMMITTED",
                           "capability": "A.LINK", "generation": 2,
                           "optimizer_step": 116776, "teacher_policy": "abc123",
                           "source_training_accuracy_before": .5,
                           "source_training_accuracy_after": .75,
                           "teacher_reward": .25, "next_phase": "MAIN"})
            shown = board.render(width=115, height=38)
            self.assertIn("LESSON COMMITTED", shown)
            self.assertIn("116776", shown)
            self.assertIn("exam pending", shown)

    def test_six_panel_renderer_still_has_same_names_and_rows(self):
        self.assertEqual([name for name,_ in TABLES],[
            "CANDIDATES","SENTINEL & RETENTION","SOUP & TEACHER",
            "BRIDGE FAMILIES","GRADES & MASTERY","SYSTEM & QUALIFICATION"])
        with tempfile.TemporaryDirectory() as tmp:
            out=io.StringIO()
            with redirect_stdout(out):
                result=main(["dashboard","--run-dir",tmp])
            self.assertEqual(result,0)
            for name,_ in TABLES:
                self.assertIn(name,out.getvalue())
            self.assertIn("READY_FOR_HUMAN_GRADE_A_START",out.getvalue())

    def test_explicit_resume_only_and_training_is_hard_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=io.StringIO()
            with redirect_stdout(output):
                code=main(["train","--dry-run","--run-dir",tmp])
            self.assertEqual(code,0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["start_behavior"], "GRADE_A_NEW_RUN")
            self.assertEqual(report["result"], "PREFLIGHT_ONLY_NO_NEURAL_UPDATES")
            self.assertFalse(report["human_live_grade_a_trainer_end_to_end_qualified"])
            self.assertEqual(report["disposable_full_student_optimizer_continuation"]["scope"],
                             "ONE_DETACHED_STEP_AND_COMPLETE_39_TENSOR_ADAMW_RESTART")
            self.assertEqual(report["blockers"], [])
            self.assertTrue(report["source_grounded_grade_a_admitted"])
            self.assertEqual(report["grade_a_release"],
                             "bilqis.mlx.grade-a-live/20261015")
            self.assertEqual(report["historical_source_release"],
                             "bilqis.mlx.grade-a-user-accepted/20261015")
            self.assertEqual(len(report["experimental_risks"]), 2)
            self.assertEqual(report["operator_constraint"], "HUMAN_ONLY_NEURAL_OPTIMIZER_UPDATES")
            self.assertNotIn("HUMAN_ONLY_NEURAL_OPTIMIZER_UPDATES", report["blockers"])
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train","--dry-run","--resume","--run-dir",tmp]),2)
                self.assertEqual(main(["train","--run-dir",tmp]),2)
            self.assertEqual(list(Path(tmp).iterdir()),[])

    @unittest.skipUnless(ORIGINAL_CHECKPOINT.is_file(), "Pinned whole student not mounted")
    def test_verified_source_preflight_is_real_not_synthetic_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["train", "--dry-run", "--verify-source", "--run-dir", tmp])
            self.assertEqual(code, 0)
            receipt = json.loads(output.getvalue())["source_manifest_preflight"]
            self.assertEqual(receipt["verified_items"], 216)
            self.assertEqual(receipt["exam_rubric_sha256"],
                             "7f351f93b81a1d08a45dd53d5f253ad34c238019015e84284d50ca40378a1370")
            self.assertFalse(receipt["original_candidate_manifest_release_flag"])
            self.assertTrue(receipt["grade_a_user_acceptance_is_separate"])
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__=="__main__":
    unittest.main()
