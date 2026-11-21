"""BAMF live dashboard refresh and execution-local header counters."""
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

from bilqis_mlx.presentation.operator_cli.bamf_resume_dispatch import (
    _live_bamf_dashboard_refresh,
)
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard


def _visit(capability, visit, step, *, outcome="ACCEPTED", candidate_step=4):
    return {
        "observation_id": f"observed-{visit}", "revision": 7,
        "run_id": "aspirant", "visit_index": visit,
        "capability_id": capability, "phase": "COMPLETED", "outcome": outcome,
        "candidate_optimizer_step": step, "candidate_step": candidate_step,
        "candidate_horizon": 4, "candidate_steps": [],
        "visit_evidence": {"state": "PARTIAL", "grade_id": "A",
                           "capability_id": capability},
    }


class BamfLiveRefreshTests(unittest.TestCase):
    def test_refreshes_without_waiting_for_progress_event(self):
        board = Mock()
        with _live_bamf_dashboard_refresh(board, interval=0.01):
            time.sleep(0.025)
        self.assertGreaterEqual(board.draw.call_count, 1)

    def test_projection_tracks_current_session_attempts_and_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "bamf-state.json").write_text(json.dumps({
                "run_id": "aspirant", "generation": 13,
            }))
            observed = run / "trainer-observed.json"
            prior = _visit("A.MEMBER", 12, 46)
            observed.write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v7", "visits": [prior],
            }))
            board = Dashboard(stream=io.StringIO(), tables=LETTER_TABLES,
                              compact_header=True, show_all_panels=True)
            board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
            board.log_hint = str(run / "events.jsonl")
            board.draw()

            current = _visit("A.LINK", 13, 50, outcome="RUNNING", candidate_step=2)
            current["revision"] = 8
            observed.write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v7", "visits": [prior, current],
            }))
            board.draw()
            self.assertEqual((board.state["visits"], board.state["retained_visits"]), (0, 0))
            self.assertEqual(board.state["attempted_steps"], 2)

            current.update(outcome="ACCEPTED", candidate_step=4, revision=9)
            observed.write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v7", "visits": [prior, current],
            }))
            board.draw()
            self.assertEqual((board.state["visits"], board.state["retained_visits"]), (1, 1))
            self.assertEqual(board.state["attempted_steps"], 4)


if __name__ == "__main__":
    unittest.main()
