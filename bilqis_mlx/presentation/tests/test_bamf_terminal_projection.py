import io
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard


def observed_visit(capability, visit, step, *, before, after, wall):
    return {
        "observation_id": f"observed-{visit}",
        "revision": 7,
        "run_id": "aspirant",
        "visit_index": visit,
        "observed_at": 1_795_195_509_000 + visit,
        "elapsed_ms": 420_000,
        "capability_id": capability,
        "phase": "COMPLETED",
        "outcome": "ACCEPTED",
        "candidate_optimizer_step": step,
        "candidate_step": 4,
        "candidate_horizon": 4,
        "retention_completed": 2,
        "retention_total": 2,
        "retention_subject": capability,
        "retention_role": "candidate",
        "peak_rss_bytes": 14_388_912_128,
        "disk_free_bytes": 278_313_880_781,
        "candidate_steps": [{
            "candidate_step": 4,
            "candidate_optimizer_step": step,
            "candidate_step_wall_seconds": wall,
            "b11_preflight_wall_seconds": 12.4,
            "b11_autodiff_wall_seconds": 12.2,
            "c08_logical_batch_wall_seconds": 31.1,
        }],
        "visit_evidence": {
            "state": "COMPLETE",
            "grade_id": "A",
            "capability_id": capability,
            "teacher_policy_key": "8694ee76cff6",
            "selected_option_id": capability,
            "protected_scope_state": "PARTIAL",
            "decision": "PROVISIONAL",
            "reason": "PAIRED_SCREEN_WITHIN_BUDGET",
            "learning_target": {
                "state": "MEASURED",
                "before": before,
                "after": after,
                "total": 6,
            },
        },
        "learning_health": {
            "state": "NOT_MEASURED",
            "qualification_state": "NOT_MEASURED",
            "gain_from_first": None,
            "warnings": [{
                "signal": "LACK_OF_DURABLE_GAIN",
                "status": "NOT_MEASURED",
                "note": "Required source evidence unavailable",
                "evidence_count": 0,
            }],
        },
        "activity": "publishing accepted successor checkpoint",
        "activity_elapsed_ms": 46_500,
        "planning_wall_seconds": 226.9,
        "retention_wall_seconds": 117.6,
        "championship_wall_seconds": 581.1,
        "publishing_wall_seconds": 3.1,
    }


class BamfTerminalProjectionTests(unittest.TestCase):
    def test_resume_keeps_durable_history_beyond_disposable_observation_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "bamf-state.json").write_text(json.dumps({
                "run_id": "aspirant", "generation": 14,
            }))
            accepted = {
                "event": "BAMF_C16_3_ACCEPTED", "event_id": "accepted-1",
                "capability": "A.EDGE", "candidate_attempt_ordinal": 11,
                "optimizer_step": 50, "selected_policy_key": "policy-a",
                "visit_id": "visit-accepted",
                "resource": {"loss_total": 0.812},
                "how_outcome": {
                    "attempted_steps": 4, "retained_steps": 4,
                    "selected_policy": {
                        "lr": 0.0003, "depth": 2, "contrast": 0.0,
                        "old": 6, "preview": 4, "distill": 0.35,
                    },
                    "protected_capabilities": [],
                    "scores": [["A.EDGE", 2, 3, 6]],
                    "decision": {
                        "decision": "PROVISIONAL", "reason": "WITHIN_BUDGET",
                        "evaluated_capability_ids": ["A.EDGE"],
                    },
                    "context": {"grade": "A", "phase": "MAIN"},
                },
            }
            rejected = {
                "event": "BAMF_CANDIDATE_REJECTED", "event_id": "rejected-1",
                "generation": 13, "optimizer_step": 50,
                "evidence": {
                    "capability": "A.PARENT", "candidate_optimizer_step": 54,
                    "rejection_attempt_ordinal": 12, "selected_policy_key": "policy-b",
                    "visit_id": "visit-rejected", "retention_reason": "NO_GAIN",
                    "how_outcome": {
                        "attempted_steps": 4, "retained_steps": 0,
                        "scores": [["A.PARENT", 3, 3, 6]],
                        "decision": {"decision": "REJECT", "reason": "NO_GAIN"},
                        "context": {"grade": "A"},
                    },
                },
            }
            (run / "events.jsonl").write_text(
                json.dumps(accepted) + "\n" + json.dumps(rejected) + "\n")
            (run / "trainer-observed.json").write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v7",
                "visits": [observed_visit("A.MAPS", 13, 58, before=4, after=5, wall=9.2)],
            }))
            board = Dashboard(
                stream=io.StringIO(), clock=lambda: 1000.0,
                tables=LETTER_TABLES, compact_header=True, show_all_panels=True)
            board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
            board.log_hint = str(run / "events.jsonl")

            board.draw()

            capabilities = [row["capability"] for row in board.rows["CANDIDATES"]]
            self.assertEqual(capabilities, ["A.EDGE", "A.PARENT", "A.MAPS"])
            accepted_candidate = board.rows["CANDIDATES"][0]
            accepted_teacher = board.rows["SOUP & TEACHER"][0]
            accepted_retention = board.rows["SENTINEL & RETENTION"][0]
            self.assertEqual(accepted_candidate["lr"], "30")
            self.assertEqual(accepted_candidate["old"], "6")
            self.assertEqual(accepted_candidate["loss"], "0.812")
            self.assertEqual(accepted_teacher["lr"], "30")
            self.assertEqual(accepted_teacher["depth"], "2")
            self.assertEqual(accepted_teacher["contrast"], "0")
            self.assertEqual(accepted_teacher["old"], "6")
            self.assertEqual(accepted_teacher["distill"], "0.350")
            self.assertEqual(accepted_teacher["p_ret"], "50.0%")
            self.assertEqual(accepted_teacher["health"], "UNCERTAIN")
            self.assertEqual(accepted_retention["protected"], "0")
            self.assertTrue(accepted_retention["evidence"].startswith("1/1 | "))

    def test_live_overlay_preserves_richer_durable_visit_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "bamf-state.json").write_text(json.dumps({
                "run_id": "aspirant", "generation": 14,
            }))
            accepted = {
                "event": "BAMF_C16_3_ACCEPTED", "event_id": "accepted-overlay",
                "capability": "A.PARENT", "candidate_attempt_ordinal": 3,
                "optimizer_step": 78, "selected_policy_key": "ad7180a27c27",
                "visit_id": "shared-visit",
                "how_outcome": {
                    "attempted_steps": 12, "retained_steps": 12,
                    "selected_policy": {
                        "lr": 0.0003, "depth": 2, "contrast": 0.0,
                        "old": 6, "preview": 4, "distill": 0.35,
                    },
                    "protected_capabilities": [],
                    "scores": [["A.PARENT", 3, 4, 6]],
                    "decision": {
                        "decision": "PROVISIONAL",
                        "reason": "PAIRED_SCREEN_WITHIN_BUDGET",
                        "evaluated_capability_ids": ["A.PARENT"],
                    },
                    "context": {"grade": "A", "phase": "RECOVERY_1"},
                },
            }
            (run / "events.jsonl").write_text(json.dumps(accepted) + "\n")
            live = observed_visit("A.PARENT", 3, 78, before=3, after=4, wall=2.2)
            live["visit_id"] = "shared-visit"
            live["visit_evidence"]["teacher_policy_key"] = "ad7180a27c27"
            (run / "trainer-observed.json").write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v7", "visits": [live],
            }))
            board = Dashboard(
                stream=io.StringIO(), clock=lambda: 1000.0,
                tables=LETTER_TABLES, compact_header=True, show_all_panels=True)
            board.school_telemetry = SchoolTelemetry(board, active_grades=("A", "B"))
            board.grade_program = ("A", "B")
            board.log_hint = str(run / "events.jsonl")

            board.draw()

            teacher = board.rows["SOUP & TEACHER"][0]
            self.assertEqual(teacher["policy"], "ad7180a27c")
            self.assertEqual(teacher["lr"], "30")
            self.assertEqual(teacher["depth"], "2")
            rendered = board.render(width=300, height=38)
            self.assertIn("EXAM PENDING", rendered)

    def test_tty_draw_projects_existing_bamf_observation_into_dense_cockpit(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "bamf-state.json").write_text(json.dumps({
                "run_id": "aspirant", "generation": 13,
            }))
            (run / "trainer-observed.json").write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v7",
                "learning_health_run_id": "aspirant",
                "visits": [
                    observed_visit("A.MEMBER", 12, 46, before=2, after=3, wall=50.7),
                    observed_visit("A.LINK", 13, 50, before=5, after=5, wall=54.4),
                ],
                "learning_health_by_capability": {},
            }))
            output = io.StringIO()
            board = Dashboard(
                stream=output, clock=lambda: 1000.0,
                tables=LETTER_TABLES, compact_header=True, show_all_panels=True,
            )
            board.school_telemetry = SchoolTelemetry(
                board, active_grades=("A", "B", "C"))
            board.grade_program = ("A", "B", "C")
            board.run_name = "aspirant"
            board.log_hint = str(run / "events.jsonl")
            board.state.update(
                phase="PERSISTENT_BAMF", prefix="A", step=50, visits=13,
                teacher=13, retained_visits=0, grew=0,
                graduations="0.0.0 / 0.0.0",
            )

            board.draw()

            self.assertEqual(len(board.rows["CANDIDATES"]), 2)
            self.assertEqual(len(board.rows["SENTINEL & RETENTION"]), 2)
            self.assertEqual(len(board.rows["SOUP & TEACHER"]), 2)
            self.assertGreaterEqual(len(board.rows["BRIDGE FAMILIES"]), 2)
            rendered = board.render(width=300, height=38)
            headings, values = rendered.splitlines()[:2]
            self.assertEqual(
                values[headings.index("EXAM"):headings.index("EXAM") + 6].strip(),
                "PEND",
            )
            self.assertEqual(values[headings.index("CAPS"):headings.index("CAPS") + 5].strip(), "-")
            self.assertRegex(rendered, r"CANDIDATES\s+\[2/2 visible\]")
            self.assertIn("A.LINK", rendered)
            self.assertIn("8694ee76", rendered)
            self.assertIn("PAIRED_SCREEN_WITHIN_BUDGET", rendered)
            self.assertIn("54.4s", rendered)
            self.assertIn("13.4 GiB", rendered)
            self.assertIn("259.2 GiB", rendered)
            self.assertIn("publishing accepted successor checkpoint", rendered)

    def test_refresh_replaces_owned_rows_and_malformed_snapshot_keeps_last_good_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "bamf-state.json").write_text(json.dumps({
                "run_id": "aspirant", "generation": 13,
            }))
            snapshot = {
                "schema": "bilqis.bamf.trainer-observed/v7",
                "visits": [
                    observed_visit("A.MEMBER", 12, 46, before=2, after=3, wall=50.7),
                    observed_visit("A.LINK", 13, 50, before=5, after=5, wall=54.4),
                ],
            }
            observed = run / "trainer-observed.json"
            observed.write_text(json.dumps(snapshot))
            board = Dashboard(
                stream=io.StringIO(), clock=lambda: 1000.0,
                tables=LETTER_TABLES, compact_header=True, show_all_panels=True,
            )
            board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
            board.log_hint = str(run / "events.jsonl")

            board.draw()
            self.assertEqual(len(board.rows["CANDIDATES"]), 2)
            observed.write_text("{broken")
            board.draw()
            self.assertEqual(len(board.rows["CANDIDATES"]), 2)

            snapshot["visits"].append(
                observed_visit("A.PARENT", 14, 54, before=4, after=5, wall=49.8))
            observed.write_text(json.dumps(snapshot))
            board.draw()
            self.assertEqual(len(board.rows["CANDIDATES"]), 3)
            self.assertEqual(
                [row["capability"] for row in board.rows["CANDIDATES"]],
                ["A.MEMBER", "A.LINK", "A.PARENT"],
            )


    def test_live_and_durable_forms_of_one_terminal_visit_count_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "bamf-state.json").write_text(json.dumps({
                "run_id": "aspirant", "generation": 20,
            }))
            historical = {
                "event": "BAMF_CANDIDATE_REJECTED", "event_id": "historical",
                "evidence": {
                    "capability": "A.EDGE", "candidate_optimizer_step": 126,
                    "rejection_attempt_ordinal": 1, "visit_id": "historical-visit",
                    "retention_reason": "NO_GAIN",
                    "how_outcome": {
                        "attempted_steps": 12, "retained_steps": 0,
                        "decision": {"decision": "REJECT", "reason": "NO_GAIN"},
                        "context": {"grade": "A"},
                    },
                },
            }
            events = run / "events.jsonl"
            events.write_text(json.dumps(historical) + "\n")
            (run / "trainer-observed.json").write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v7", "visits": [],
            }))
            board = Dashboard(
                stream=io.StringIO(), clock=lambda: 1000.0,
                tables=LETTER_TABLES, compact_header=True, show_all_panels=True)
            board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
            board.log_hint = str(events)

            board.draw()
            self.assertEqual(board.state["visits"], 0)

            accepted = {
                "event": "BAMF_C16_3_ACCEPTED", "event_id": "accepted-current",
                "capability": "A.MAPS", "candidate_attempt_ordinal": 1,
                "optimizer_step": 138, "selected_policy_key": "policy-current",
                "visit_id": "authoritative-visit-id",
                "how_outcome": {
                    "attempted_steps": 12, "retained_steps": 12,
                    "scores": [["A.MAPS", 3, 4, 6]],
                    "decision": {
                        "decision": "PROVISIONAL", "reason": "WITHIN_BUDGET",
                        "evaluated_capability_ids": ["A.MAPS"],
                    },
                    "context": {"grade": "A", "phase": "RECOVERY_1"},
                },
            }
            events.write_text(
                json.dumps(historical) + "\n" + json.dumps(accepted) + "\n")
            live = observed_visit("A.MAPS", 13, 138, before=3, after=4, wall=2.1)
            live.pop("visit_id", None)
            (run / "trainer-observed.json").write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v7", "visits": [live],
            }))

            board.draw()

            self.assertEqual(board.state["visits"], 1)
            self.assertEqual(board.state["retained_visits"], 1)
            self.assertEqual(board.state["attempted_steps"], 12)
            self.assertEqual(
                [row["capability"] for row in board.rows["CANDIDATES"]].count("A.MAPS"),
                1,
            )


if __name__ == "__main__":
    unittest.main()
