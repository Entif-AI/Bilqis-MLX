"""Grade-neutral School50 evidence, including future grades and empty channels."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from bilqis_mlx.grade_a_dashboard import build, ingest
from bilqis_mlx.spiral_dashboard import Dashboard, TABLES


def exam(grade, generation, rubric, scores, *, step, sha="signed-model"):
    return {"event": "SCHOOL_EXAM_COMMITTED", "grade": grade,
            "generation": generation, "rubric": rubric,
            "optimizer_step": step, "student_sha256": sha, "phase": "MAIN",
            "scores": {cap: {"correct": correct, "total": total}
                       for cap, (correct, total) in scores.items()}}


class SchoolTelemetryTests(unittest.TestCase):
    def test_retention_decision_not_instructional_note_controls_commit_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for cap, decision, reason, updates in (
                ("C.NUMBER", "REJECT", "NO_MEASURABLE_TARGET_GAIN", 0),
                ("C.MUL", "REJECT", "FRAGILE_COMPOSITION_REPLAY_REGRESSION", 0),
                ("B.NOT", "PROVISIONAL", "PAIRED_SCREEN_WITHIN_BUDGET", 16),
            ):
                ingest(board, {
                    "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                    "capability": cap, "grade": cap[0],
                    "optimizer_step": 229512,
                    "retained_optimizer_updates": updates,
                    "candidate_retention": {"decision": decision, "reason": reason},
                    "teacher_decision": {"selected": {"exam_mistake_replay": 1}},
                })
            c_number, c_mul, b_not = list(board.rows["CANDIDATES"])[-3:]
            self.assertIn("REJECT", c_number["decision"])
            self.assertIn("NO TARGET GAIN", c_number["decision"])
            self.assertNotIn("LESSON COMMITTED", c_number["decision"])
            self.assertIn("REJECT", c_mul["decision"])
            self.assertIn("OR/XOR", c_mul["decision"])
            self.assertIn("RETAIN 16", b_not["decision"])
            self.assertIn("miss 1", b_not["decision"])
            self.assertNotIn("LESSON COMMITTED", b_not["decision"])

    def test_inconsistent_retention_metadata_does_not_claim_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "C", "capability": "C.NUMBER",
                "retained_optimizer_updates": 0,
                "candidate_retention": {"decision": "PROVISIONAL",
                                        "reason": "PAIRED_SCREEN_WITHIN_BUDGET"}})
            self.assertIn("ADMISSION CONFLICT",
                          board.rows["CANDIDATES"][-1]["decision"])

    def test_unavailable_longitudinal_history_names_the_actual_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 22, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64, "optimizer_step": 123,
                "cohort_file": f"cohorts/{'c' * 64}.json",
                "generator_version": "test-fixed-b-cohort/v1",
                "student_sha256": "a" * 64,
                "scores": {"B.OR": {"correct": 11, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [], "history_usable": False,
                    "history_issue": "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY",
                    "findings": [{"status": "NOT_MEASURED", "signal": "LACK_OF_DURABLE_GAIN",
                                  "capability": "B.OR"}]}})
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            self.assertIn("S3 unavailable", diagnostic["detail"])
            self.assertIn("1 NOT MEASURED", diagnostic["detail"])
            self.assertNotIn("no active warnings", diagnostic["detail"])
            history_error = next(row for row in system if row["kind"] == "HISTORY ISSUE")
            self.assertEqual(history_error["detail"],
                             "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY")

    def test_paired_s3_recovery_does_not_keep_unavailable_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 23, "rubric": "b" * 64,
                "cohort_sha256": "d" * 64, "optimizer_step": 139,
                "cohort_file": f"cohorts/{'d' * 64}.json",
                "generator_version": "fresh-b-cohort/v2",
                "student_sha256": "e" * 64,
                "scores": {"B.OR": {"correct": 10, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [{"signal": "LACK_OF_DURABLE_GAIN",
                                         "capability": "B.OR", "target": "CAPABILITY"}],
                    "history_usable": False, "s3_usable": True,
                    "history_issue": "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY",
                    "findings": [{"status": "OBSERVED_LONGITUDINALLY",
                                  "signal": "LACK_OF_DURABLE_GAIN",
                                  "capability": "B.OR"}]}})
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            self.assertIn("S3:B.OR", diagnostic["detail"])
            self.assertNotIn("S3 unavailable", diagnostic["detail"])
            history_error = next(row for row in system if row["kind"] == "HISTORY ISSUE")
            self.assertIn("paired S3 recovered", history_error["detail"])

    def test_lesson_accuracy_is_not_labeled_as_cumulative_exam(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            labels = [column.name for column in dict(board.tables)["CANDIDATES"]]
            self.assertIn("LESSON% BFR>AFTER", labels)
            self.assertNotIn("TRAIN BEFORE>AFTER", labels)

    def test_rotating_live_cohort_exams_never_report_cross_sample_gain(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for number, total in ((1, 5), (2, 9)):
                ingest(board, {
                    "event": "GRADE_A_LIVE_EXAM_COMMITTED",
                    "generation": number, "rubric": "a"*64,
                    "cohort_sha256": str(number)*64,
                    "generator_version": "grade-a-live/v1",
                    "cohort_file": f"cohorts/{str(number)*64}.json",
                    "optimizer_step": 100 + number,
                    "student_sha256": str(number)*64,
                    "scores": {"A.IDENTITY": {"correct": total, "total": 12}},
                })
            latest = board._section_rows("BRIDGE FAMILIES")[-1]
            self.assertEqual(latest["before"], "-")
            self.assertEqual(latest["gain"], "-")
            self.assertIn("GENERATED COHORT", board._section_rows("SENTINEL & RETENTION")[-1]["evidence"])
            rendered = board.render(width=180, height=42)
            self.assertIn("BEST OBSERVED SAMPLE (not paired)", rendered)
            self.assertIn("fresh sampled cohort", rendered)

    def test_both_grades_use_live_144_item_cohorts_without_unpaired_gains(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp),stream=io.StringIO())
            for index, a_score, b_score in ((1,65,41),(2,70,49)):
                ingest(board,{"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                    "grade":"B", "generation":index,
                    "rubric":"b"*64, "cohort_sha256":str(index)*64,
                    "generator_version":"bilqis.mlx.grade-b-connectives-constructor/v1",
                    "cohort_file":f"cohorts/{str(index)*64}.json",
                    "optimizer_step":153144+index,
                    "student_sha256":str(index)*64,
                    "scores":{
                        "A.IDENTITY":{"correct":a_score%12,"total":12},
                        "A.PARENT":{"correct":a_score//12,"total":12},
                        "B.NOT":{"correct":b_score%12,"total":12},
                        "B.AND":{"correct":b_score//12,"total":12}},
                })
            mastery = {row["grade"]:row for row in
                       board._section_rows("GRADES & MASTERY")}
            self.assertEqual(set(mastery),{"A","B"})
            self.assertEqual(mastery["B"]["latest"],"5/24")
            self.assertEqual(board._section_rows("BRIDGE FAMILIES")[-1]["gain"],"-")
            self.assertTrue(any("GENERATED COHORT" in event["evidence"] for event in
                                board._section_rows("SENTINEL & RETENTION")))

    def test_independent_perfect_grade_bests_do_not_claim_cumulative_graduation(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for generation, a, b in ((1, 12, 10), (2, 8, 12), (3, 11, 11)):
                ingest(board, {
                    "event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "grade": "B",
                    "generation": generation, "rubric": "b" * 64,
                    "cohort_sha256": str(generation) * 64,
                    "generator_version": "grade-b-live/v1",
                    "cohort_file": f"cohorts/{str(generation)*64}.json",
                    "optimizer_step": 200 + generation,
                    "student_sha256": str(generation) * 64,
                    "phase": "RECOVERY_1",
                    "scores": {"A.IDENTITY": {"correct": a, "total": 12},
                               "B.NOT": {"correct": b, "total": 12}},
                })
            grades = {row["grade"]: row for row in
                      board._section_rows("GRADES & MASTERY")}
            self.assertEqual(grades["A"]["best"], "12/12")
            self.assertEqual(grades["B"]["best"], "12/12")
            rows = [row for row in board.rows["SYSTEM & QUALIFICATION"]
                    if row["kind"] == "CUMULATIVE"]
            self.assertEqual(len(rows), 1)
            self.assertIn("latest 22/24", rows[0]["detail"])
            self.assertIn("best same student 22/24", rows[0]["detail"])
            self.assertIn("24/24 REQUIRED", rows[0]["detail"])
            self.assertIn("CUMULATIVE", " ".join(board.operator_lines))
            self.assertNotIn("QUALIFIED", " ".join(board.operator_lines))

            ingest(board, {"event": "SCHOOL_SESSION_STOPPED", "grade": "B",
                           "stop_reason": "TIME_LIMIT_REACHED",
                           "visits_this_command": 3, "elapsed_seconds": 5401.,
                           "optimizer_step": 203})
            self.assertIn("TIME_LIMIT_REACHED", board.mode)
            self.assertIn("24/24 REQUIRED", " ".join(board.operator_lines))

    def test_cumulative_perfect_requires_one_complete_scored_student(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                "grade": "B", "generation": 1, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64, "cohort_file": f"cohorts/{'c'*64}.json",
                "generator_version": "grade-b-live/v1", "optimizer_step": 300,
                "student_sha256": "d" * 64, "phase": "AWAITING_NEXT_GRADE",
                "scores": {"A.IDENTITY": {"correct": 12, "total": 12},
                           "B.NOT": {"correct": 12, "total": 12}}})
            rows = [row for row in board.rows["SYSTEM & QUALIFICATION"]
                    if row["kind"] == "CUMULATIVE"]
            self.assertEqual(len(rows), 1)
            self.assertIn("24/24", rows[0]["detail"])
            self.assertIn("GATE MET", rows[0]["detail"])

    def test_cumulative_backward_a_replay_shows_a_as_exam_target_not_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp),stream=io.StringIO())
            ingest(board,{"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                "grade":"A","phase":"MAIN","generation":27,
                "rubric":"b"*64,"cohort_sha256":"8"*64,
                "generator_version":"bilqis.mlx.grade-b-connectives-constructor/v1",
                "cohort_file":f"cohorts/{'8'*64}.json",
                "optimizer_step":154008,"student_sha256":"8"*64,
                "scores":{"A.IDENTITY":{"correct":12,"total":12},
                           "B.NOT":{"correct":9,"total":12}}})
            self.assertEqual(board.school_telemetry.last_exam_grade,"A")
            self.assertIn("LATEST A 12/12",board.operator_lines[0])
            self.assertEqual(board.state["prefix"],"A")

    def test_saved_b_grade_dashboard_shows_current_cumulative_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            state = {"curriculum_mode":"bilqis.mlx.grade-a-b-live/20261015-v1",
                "result":"GRADE_B_REVALIDATING_A", "teacher":{"events":4000},
                "school":{"stage":"MAIN", "active_grades":["A","B"],
                    "grade_index":0,"visits":1000,
                    "current_student":{"optimizer_step":154000},
                    "champions":{}},"last_exam":None}
            (run/"state.json").write_text(json.dumps(state))
            board = build(run,stream=io.StringIO())
            source = next(row["detail"] for row in
                          board.rows["SYSTEM & QUALIFICATION"]
                          if row["kind"]=="RUBRIC")
            self.assertIn("generated 144",source)
            self.assertIn("same-checkpoint",source)

    def test_six_legacy_panel_names_remain_but_new_school_columns_are_useful(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            self.assertEqual(set(board.rows), {name for name, _ in TABLES})
            self.assertEqual([x.name for x in dict(board.tables)["CANDIDATES"]][:3],
                             ["CAPABILITY", "VISIT", "POLICY"])
            self.assertEqual([x.name for x in dict(TABLES)["CANDIDATES"]][:3],
                             ["GRADE", "TRY", "STRATEGY"])
            self.assertTrue(Dashboard(stream=io.StringIO()).rows)

    def test_capability_best_below_perfect_is_displayed_without_grade_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_CAPABILITY_BEST_COMMITTED",
                           "grade": "A", "optimizer_step": 116776,
                           "student_sha256": "e" * 64,
                           "rubric": "a" * 64,
                           "scores": {"A.IDENTITY": {"correct": 5, "total": 12},
                                      "A.LINK": {"correct": 7, "total": 12}},
                           "capabilities": ["A.IDENTITY", "A.LINK"]})
            message = board.rows["SYSTEM & QUALIFICATION"][-1]["detail"]
            self.assertIn("A.IDENTITY", message)
            self.assertIn("A.LINK", message)
            self.assertIn("NOT grade mastery", message)
            self.assertFalse(board.rows["SENTINEL & RETENTION"])

    def test_real_source_visit_shows_strategy_loss_reward_and_no_fake_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "GRADE_A_TEACHER_VISIT_COMMITTED",
                           "generation": 2, "capability": "A.IDENTITY",
                           "optimizer_step": 116776, "teacher_policy": "c0d92a80eada",
                           "strategy": {"lr": .00013, "depth": 1, "contrast": 1.,
                                        "old": 16, "preview": 4, "distill": .15},
                           "unavailable_teacher_dimensions": ["old", "preview", "distill"],
                           "source_training_accuracy_before": 7/12,
                           "source_training_accuracy_after": 11/12,
                           "teacher_reward": 4/12, "gradient_norm": 1.26,
                           "loss": .467, "next_phase": "MAIN",
                           "teacher_decision": {
                               "warning_signals": ["DISCONNECTED_PREREQUISITES"],
                               "selected": {"exam_mistake_replay": 2,
                                            "champion_priority": 1},
                           }})
            candidate = board.rows["CANDIDATES"][-1]
            teacher = board.rows["SOUP & TEACHER"][-1]
            self.assertEqual(candidate["capability"], "A.IDENTITY")
            self.assertIn("58.3", candidate["train"])
            self.assertIn("91.7", candidate["train"])
            self.assertEqual(candidate["reward"], "+0.333")
            self.assertEqual(teacher["old"], "OFF")
            self.assertEqual(teacher["preview"], "OFF")
            self.assertEqual(teacher["distill"], "OFF")
            self.assertIn("0.467", candidate["loss"])
            self.assertIn("1.26", candidate["gradient"])
            self.assertIn("S4", candidate["decision"])
            self.assertIn("miss 2", candidate["decision"])
            self.assertIn("champ 1", candidate["decision"])
            self.assertFalse(board.rows["SENTINEL & RETENTION"])
            self.assertTrue(any("NOT MEASURED" in x["detail"]
                                for x in board.rows["SYSTEM & QUALIFICATION"]))

    def test_live_exam_projects_warning_and_teacher_outcome_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 8, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64,
                "generator_version": "grade-b-live/v1",
                "cohort_file": f"cohorts/{'c'*64}.json",
                "optimizer_step": 200, "student_sha256": "d" * 64,
                "scores": {"B.NOT": {"correct": 6, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [{"signal":"CHANCE_LEVEL_OR_LAGGING",
                                         "target":"CAPABILITY","capability":"B.NOT"}],
                    "findings": [{"signal":"CHANCE_LEVEL_OR_LAGGING",
                                  "status":"OBSERVED_IN_COHORT","capability":"B.NOT"},
                                 {"signal":"LACK_OF_DURABLE_GAIN",
                                  "status":"NOT_MEASURED","capability":"B.NOT"}],
                },
                "teacher_outcomes": [{
                    "capability":"B.NOT",
                    "attribution":"MEASURED_FIXED_EXAM_UNIQUE_ACTION",
                    "delta_correct": 2,
                }],
            })
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            outcome = next(row for row in system if row["kind"] == "TEACH OUTCOME")
            self.assertIn("S2:B.NOT", diagnostic["detail"])
            self.assertIn("1 NOT MEASURED", diagnostic["detail"])
            self.assertIn("B.NOT +2", outcome["detail"])

    def test_first_latest_best_and_regression_use_same_sealed_rubric(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for index, numbers in enumerate(((7, 5), (10, 8), (6, 4)), 1):
                ingest(board, exam("A", index * 5, "rubric-a",
                    {"A.IDENTITY": (numbers[0], 12), "A.PARENT": (numbers[1], 12)},
                    step=116760 + 16 * index))
            rows = board._section_rows("BRIDGE FAMILIES")
            self.assertEqual(len(rows), 2)
            identity = next(r for r in rows if r["family"] == "A.IDENTITY")
            self.assertEqual(identity["first"], "7/12")
            self.assertEqual(identity["before"], "10/12")
            self.assertEqual(identity["after"], "6/12")
            self.assertEqual(identity["gain"], "-4")
            mastery = board._section_rows("GRADES & MASTERY")
            self.assertEqual(len(mastery), 1)
            self.assertEqual(mastery[0]["latest"], "10/24")
            self.assertEqual(mastery[0]["best"], "18/24")
            self.assertEqual(mastery[0]["to100"], "14")
            text = board.render(width=180, height=42)
            self.assertIn("FIRST SEALED A 12/24", text)
            self.assertIn("LATEST A 10/24", text)
            self.assertIn("BEST A 18/24", text)
            self.assertIn("TO100 14/24", text)

    def test_future_b_cumulative_exam_preserves_per_grade_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, exam("A", 8, "rubric-a", {"A.IDENTITY": (9, 12)},
                               step=117000, sha="old-a"))
            ingest(board, exam("B", 12, "rubric-a+b", {
                "A.IDENTITY": (8, 12), "B.DIRECTION": (11, 12)},
                step=117500, sha="whole-a+b"))
            mastery = {r["grade"]: r for r in board._section_rows("GRADES & MASTERY")}
            self.assertEqual(set(mastery), {"A", "B"})
            self.assertEqual(mastery["A"]["latest"], "8/12")
            self.assertEqual(mastery["B"]["latest"], "11/12")
            self.assertEqual(mastery["A"]["step"], 117500)
            identity = next(r for r in board._section_rows("BRIDGE FAMILIES")
                            if r["family"] == "A.IDENTITY")
            self.assertEqual(identity["gain"], "-")
            self.assertEqual(identity["before"], "-")
            self.assertTrue(all(not r.get("mastered", False) for r in mastery.values()))

    def test_future_sentinel_soup_and_qualification_emit_without_grade_renames(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_SENTINEL_COMMITTED", "grade": "C",
                           "generation": 50, "optimizer_step": 131000,
                           "partition": "independent_validation", "probe_delta_pp": 5.,
                           "dataset_sha256": "a" * 64, "student_sha256": "b" * 64,
                           "sentinel_delta_pp": 2.5, "worst_delta_pp": -6.25,
                           "cross_entropy_delta": -.3, "correct_probability_delta": .03,
                           "margin_delta": .12, "family_count": 8})
            ingest(board, {"event": "SCHOOL_SOUP_COMMITTED", "grade": "C",
                           "generation": 51, "optimizer_step": 131000,
                           "teacher_only": True, "teacher_digest": "c" * 64,
                           "soup_kl": .04, "parent_kl": .03,
                           "coverage": .85, "supervised_loss": .7,
                           "teacher_credit": .2, "bridge_ce": .4})
            ingest(board, {"event": "SCHOOL_QUALIFICATION_COMMITTED", "grade": "C",
                           "generation": 52, "status": "SOURCE_ATTESTED",
                           "details": "NI typed morphology checked"})
            self.assertEqual(board.rows["SENTINEL & RETENTION"][-1]["grade"], "C")
            self.assertEqual(board.rows["SENTINEL & RETENTION"][-1]["sent"], "+2.5pp")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["soup"], "0.040")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["cover"], "85.0%")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["sup"], "0.700")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["bridge_ce"], "0.400")
            self.assertTrue(any("SOURCE_ATTESTED" in r["detail"]
                                for r in board.rows["SYSTEM & QUALIFICATION"]))

    def test_unverified_future_sentinel_and_student_soup_cannot_claim_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            with self.assertRaisesRegex(ValueError, "SOURCE_PROVENANCE_REQUIRED"):
                ingest(board, {"event": "SCHOOL_SENTINEL_COMMITTED", "grade": "B",
                               "partition": "independent_validation", "probe_delta_pp": 5})
            with self.assertRaisesRegex(ValueError, "TEACHER_ONLY_REQUIRED"):
                ingest(board, {"event": "SCHOOL_SOUP_COMMITTED", "grade": "B",
                               "teacher_only": False, "soup_kl": .01})
            self.assertFalse(board.rows["SENTINEL & RETENTION"])
            self.assertFalse(board.rows["SOUP & TEACHER"])

    def test_future_schema_version_must_not_silently_reinterpret_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            with self.assertRaisesRegex(ValueError, "UNSUPPORTED_SCHEMA"):
                ingest(board, {"event": "SCHOOL_VISIT_COMMITTED", "grade": "Z",
                               "telemetry_schema": "bilqis.school50.telemetry/v999",
                               "capability": "Z.UNKNOWN", "optimizer_step": 300000})
            self.assertFalse(board.rows["CANDIDATES"])

    def test_disk_headroom_is_visible_and_grade_neutral_in_system_panel(self):
        free = int(100.28 * 1024 ** 3)
        with tempfile.TemporaryDirectory() as tmp, patch(
            "bilqis_mlx.disk.shutil.disk_usage",
            return_value=SimpleNamespace(total=1000 * 1024 ** 3,
                                         used=0, free=free)):
            board = build(Path(tmp), stream=io.StringIO())
            disk = next(x for x in board.rows["SYSTEM & QUALIFICATION"]
                        if x["kind"] == "DISK")
            self.assertIn("100.28 GiB", disk["detail"])
            self.assertIn("BLOCKED", disk["detail"])
            ingest(board, {"event": "SCHOOL_RESOURCE_OBSERVED", "grade": "B",
                           "free_bytes": free + 1024 ** 3,
                           "reserve_bytes": 100 * 1024 ** 3,
                           "estimated_write_bytes": 600_000_000})
            updated = [x for x in board.rows["SYSTEM & QUALIFICATION"]
                       if x["kind"] == "DISK"]
            self.assertEqual(len(updated), 1)
            self.assertIn("READY", updated[0]["detail"])

    def test_future_constructed_family_probes_have_lineage_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_FAMILY_PROBE_COMMITTED", "grade": "B",
                           "generation": 51, "family": "B.CASE.CONTRAST",
                           "before": {"correct": 3, "total": 10},
                           "after": {"correct": 8, "total": 10},
                           "partition": "independent_validation", "dataset_sha256": "a" * 64,
                           "student_sha256": "b" * 64, "optimizer_step": 132000})
            family = board._section_rows("BRIDGE FAMILIES")[-1]
            self.assertEqual(family["family"], "B.CASE.CONTRAST")
            self.assertEqual(family["before"], "3/10")
            self.assertEqual(family["after"], "8/10")
            self.assertEqual(family["gain"], "+5")
            self.assertFalse(board.rows["GRADES & MASTERY"][-1].get("mastered", False))
            with self.assertRaisesRegex(ValueError, "SOURCE_PROVENANCE_REQUIRED"):
                ingest(board, {"event": "SCHOOL_FAMILY_PROBE_COMMITTED", "grade": "B",
                               "family": "B.CASE.CONTRAST", "before": {"correct": 3, "total": 10},
                               "after": {"correct": 10, "total": 10}})

    def test_mismatched_checkpoint_in_one_exam_cannot_claim_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            corrupted = exam("A", 1, "rubric-a", {"A.IDENTITY": (12, 12)},
                             step=117000, sha="whole")
            corrupted["scores"]["A.IDENTITY"]["checkpoint_sha256"] = "different"
            with self.assertRaisesRegex(ValueError, "CHECKPOINT_MISMATCH"):
                ingest(board, corrupted)
            self.assertTrue(all(row.get("latest") == "-"
                                for row in board.rows["GRADES & MASTERY"]))

    def test_old_wide_three_pane_format_keeps_decisive_new_metrics_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "GRADE_A_TEACHER_VISIT_COMMITTED",
                           "generation": 2, "capability": "A.IDENTITY", "optimizer_step": 116776,
                           "teacher_policy": "policyabc0123",
                           "strategy": {"lr": .00013, "depth": 2, "contrast": 1},
                           "source_training_accuracy_before": .50,
                           "source_training_accuracy_after": 1.0,
                           "teacher_reward": .5, "loss": .123,
                           "gradient_norm": 1.2e-10, "next_phase": "MAIN"})
            for gen, score in ((3, 6), (6, 8)):
                ingest(board, exam("A", gen, "rubric-a",
                                   {"A.IDENTITY": (score, 12)}, step=116776 + gen))
            display = board.render(width=276, height=40)
            self.assertIn("LOSS", display)
            self.assertIn("GRAD", display)
            self.assertIn("FIRST", display)
            self.assertIn("LATEST", display)
            self.assertIn("BEST", display)
            self.assertIn("TO100", display)
            self.assertIn("GAIN", display)
            self.assertIn("+2", display)
            self.assertIn("1.2e-10", display)

    def test_generalization_gap_is_observational_not_an_optimizer_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_VISIT_COMMITTED", "grade": "B",
                           "capability": "B.RULE", "generation": 1,
                           "optimizer_step": 150000,
                           "source_training_accuracy_before": 1.,
                           "source_training_accuracy_after": 1.,
                           "teacher_reward": 0., "teacher_policy": "existing"})
            ingest(board, exam("B", 2, "rubric-b", {"B.RULE": (6, 12)},
                               step=150000))
            self.assertTrue(any("GENERALIZATION GAP" in line
                                for line in board.operator_lines))
            self.assertTrue(any("recent source-train" in line.lower()
                                for line in board.operator_lines))
            self.assertEqual(board.rows["GRADES & MASTERY"][-1]["to100"], "6")

    def test_historical_champion_does_not_hide_latest_grade_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "state.json").write_text(json.dumps({
                "school": {"active_grades": ["A", "B"],
                           "current_student": {"optimizer_step": 123400},
                           "champions": {"A": {"optimizer_step": 123000}},
                           "stage": "MAIN", "visits": 4},
                "teacher": {"events": 10}, "result": "ACTIVE_SCHOOL"}))
            board = build(run, stream=io.StringIO())
            ingest(board, exam("B", 5, "rubric-a+b", {
                "A.IDENTITY": (7, 12), "B.FOCUS": (8, 12)},
                step=123400, sha="student-B-step"))
            latest_a = next(x for x in board._section_rows("GRADES & MASTERY")
                            if x["grade"] == "A")
            self.assertTrue(latest_a["mastered"])
            self.assertIn("CURRENT REGRESSION", latest_a["outcome"])
            self.assertEqual(latest_a["latest"], "7/12")
            self.assertEqual(board.state["prefix"], "B")
            self.assertEqual(board.grade_program, ("A", "B"))


if __name__ == "__main__":
    unittest.main()
