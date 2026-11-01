"""A durable outbox is the observation commit authority across cold restart."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime import checkpoints
from bilqis_mlx.runtime.teacher_observation_capture import store_sidecar
from bilqis_mlx.runtime.teacher_observation_replay import read_committed_observations
from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.state_dag import read_current


class ObservationReplayTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.environment = patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()
        close_data_planes()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(self.environment.stop)
        self.addCleanup(close_data_planes)

    def pending_event(self, attempt="one", *, target=1):
        proposal = {"attempt_id": attempt, "selected_option": "source.direct/fixture"}
        proposal_ref = store_sidecar(self.root, proposal)
        envelope = {"schema": "bilqis.factory.teacher-observation/v1", "attempt_id": attempt,
                    "proposal_id": proposal_ref["sha256"], "proposal": proposal_ref,
                    "steps": [], "outcome": {"target": target}}
        return {"event": "SCHOOL_TEACHER_VISIT_COMMITTED", "generation": 1,
                "teacher_observation": {"attempt_id": attempt,
                    "proposal_id": proposal_ref["sha256"], "envelope": store_sidecar(self.root, envelope)}}

    def commit(self, events):
        record = {"generation": 1, "run_id": "disposable-observation-run",
                  "school": {"active_grades": ["fixture"], "grade_index": 0,
                             "current_student": {"sha256": "a" * 64,
                                 "optimizer_step": 7, "filename": "bundles/fixture", "model_and_native_adamw": True}}}
        boundary = checkpoints._boundary_delivery_events(record, events, (), None)
        return checkpoints._persist(self.root, checkpoints._with_delivery_outbox(record, boundary))

    def test_crash_before_event_emission_cold_read_and_replay_once(self):
        record = self.commit([self.pending_event()])
        self.assertFalse((self.root / "events.jsonl").exists())
        cold = read_committed_observations(self.root)
        self.assertEqual(len(cold), 1)
        self.assertEqual(cold[0]["ledger_delivery"], "OUTBOX_COMMITTED_NOT_EMITTED")
        self.assertEqual(cold[0]["publication"]["checkpoint"], record["school"]["current_student"])
        with redirect_stdout(io.StringIO()):
            checkpoints._reconcile_delivery_outbox(self.root, read_current(self.root))
            before = (self.root / "events.jsonl").read_bytes()
            checkpoints._reconcile_delivery_outbox(self.root, read_current(self.root))
        self.assertEqual((self.root / "events.jsonl").read_bytes(), before)
        self.assertEqual(len(before.splitlines()), 1)
        after = read_committed_observations(self.root)
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0]["ledger_delivery"], "EMITTED")
        self.assertEqual(after[0]["event_id"], cold[0]["event_id"])
        self.assertEqual(read_current(self.root), record)

    def test_distinct_attempts_on_same_checkpoint_are_not_collapsed(self):
        self.commit([self.pending_event("one"), self.pending_event("two")])
        observed = read_committed_observations(self.root)
        self.assertEqual({item["attempt_id"] for item in observed}, {"one", "two"})
        self.assertEqual(len({item["publication"]["checkpoint"]["sha256"] for item in observed}), 1)

    def test_divergent_duplicate_attempt_is_rejected(self):
        self.commit([self.pending_event("same", target=1), self.pending_event("same", target=2)])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ATTEMPT"):
            read_committed_observations(self.root)

    def test_forged_journal_publication_is_not_commit_authority(self):
        record = self.commit([self.pending_event()])
        forged = deepcopy(record["delivery_outbox"][0])
        forged["teacher_observation_publication"]["checkpoint"]["optimizer_step"] = 8
        (self.root / "events.jsonl").write_text(json.dumps(forged) + "\n")
        with self.assertRaisesRegex(ValueError, "TEACHER_OBSERVATION.INVALID"):
            read_committed_observations(self.root)

    def test_staged_sidecar_is_not_a_durable_observation(self):
        self.pending_event()
        checkpoints._persist(self.root, {"generation": 1, "run_id": "empty", "school": {}})
        self.assertEqual(read_committed_observations(self.root), [])
