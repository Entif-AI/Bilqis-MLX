"""Context-native C09 requalification projection into the C10 outbox."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.akasha_outbox import (
    AkashaEventKind,
    append_context_requalification,
    pending_events,
    read_outbox,
)
from bilqis_mlx.runtime.atlas_requalification import (
    CapabilitySupport,
    RequalificationLedger,
    RequalificationStatus,
    TargetedSourceTask,
)
from bilqis_mlx.runtime.accepted_correction_runtime import (
    AcceptedCorrectionRuntime,
)
from bilqis_mlx.runtime.accepted_stale_replay_runtime import (
    _flush_context_requalifications,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.authority.accepted_context_revalidation_support import (
    AUTHORITY,
)


CONTEXT_EVENT_ID = "b" * 64
CONTEXT_RECEIPT_ID = "c" * 64
GENERATION = "d" * 64
TEMPORAL_IDENTITY = {
    "source_time": 10,
    "effective_time": 20,
    "observed_at": 15,
    "recorded_at": 16,
    "authority_registry_sha256": "e" * 64,
    "schema_version": "bilqis.source-context-temporal-identity/v1",
}


def _ledger(status=RequalificationStatus.REQUALIFICATION_REQUIRED):
    support = CapabilitySupport(
        capability_id="capability:context",
        support_artifact_ids=("capability:context",),
        source_anchor_ids=("source:context",),
        retained_generation_sha256=GENERATION,
        observation_ids=("observation:context",),
        status=status,
    )
    return RequalificationLedger((support,)), TargetedSourceTask.from_context(
        support, CONTEXT_EVENT_ID)


def _pending_ledger():
    ledger, task = _ledger()
    return RequalificationLedger(
        ledger.capabilities,
        pending_source_tasks=(task,),
    ), task


def _context_record(context_event_id=CONTEXT_EVENT_ID):
    return {
        "event": "BAMF_C09_CONTEXT_INVALIDATION",
        "event_id": CONTEXT_RECEIPT_ID,
        "context_invalidation": {"context_event_id": context_event_id},
        "source_temporal_identity": dict(TEMPORAL_IDENTITY),
    }


class AkashaOutboxContextTests(unittest.TestCase):
    @patch(
        "bilqis_mlx.runtime.akasha_outbox.contexts._accepted_context_record",
        return_value=_context_record(),
    )
    @patch(
        "bilqis_mlx.runtime.akasha_outbox.contexts._context_temporal_identity",
        return_value=TEMPORAL_IDENTITY,
    )
    def test_context_task_enqueues_exactly_once_with_source_owned_time(
        self, _identity, _record,
    ):
        ledger, task = _ledger()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "outbox.sqlite3"
            run_dir = Path(folder)
            self.assertEqual(
                append_context_requalification(
                    path, run_dir, GENERATION, task, ledger),
                1,
            )
            self.assertEqual(
                append_context_requalification(
                    path, run_dir, GENERATION, task, ledger),
                0,
            )
            event = pending_events(path)[0]
            self.assertIs(event.kind, AkashaEventKind.REQUALIFICATION)
            self.assertEqual(event.subject_id, task.capability_id)
            self.assertEqual(event.source_receipt_sha256, CONTEXT_RECEIPT_ID)
            self.assertEqual(
                (event.source_time, event.effective_time,
                 event.observed_at, event.recorded_at),
                (10, 20, 15, 16),
            )
            self.assertIn(CONTEXT_EVENT_ID, event.payload_json)
            self.assertIn(task.task_id, event.payload_json)
            self.assertEqual(len(read_outbox(path)), 1)

    @patch(
        "bilqis_mlx.runtime.akasha_outbox.contexts._accepted_context_record",
        side_effect=lambda _run, _manifest, event_id: _context_record(event_id),
    )
    @patch(
        "bilqis_mlx.runtime.akasha_outbox.contexts._context_temporal_identity",
        return_value=TEMPORAL_IDENTITY,
    )
    def test_context_task_rejects_receipt_or_support_drift(
        self, _identity, _record,
    ):
        ledger, task = _ledger()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "outbox.sqlite3"
            qualified, _ = _ledger(RequalificationStatus.QUALIFIED)
            with self.assertRaises(BilqisError):
                append_context_requalification(
                    path, Path(folder), GENERATION, task, qualified)

    @patch("bilqis_mlx.runtime.akasha_outbox.append_context_requalification")
    def test_cold_flush_projects_v2_but_never_fabricates_v1_time(self, append):
        ledger, task = _pending_ledger()
        retained = type("Retained", (), {
            "run_dir": Path("/tmp/bamf-911-context"),
            "manifest_sha256": GENERATION,
        })()
        v2 = _context_record()
        v2["context_invalidation"]["schema_version"] = (
            "bilqis.c09-context-invalidation/v2")
        _flush_context_requalifications(retained, ledger, (v2,))
        append.assert_called_once_with(
            retained.run_dir / "akasha-outbox.sqlite3",
            retained.run_dir,
            GENERATION,
            task,
            ledger,
        )

        append.reset_mock()
        v1 = _context_record()
        v1["context_invalidation"]["schema_version"] = (
            "bilqis.c09-context-invalidation/v1")
        _flush_context_requalifications(retained, ledger, (v1,))
        append.assert_not_called()
        with self.assertRaises(BilqisError):
            _flush_context_requalifications(retained, ledger, ())

    @patch(
        "bilqis_mlx.runtime.accepted_stale_replay_runtime."
        "replay_stale_evidence"
    )
    def test_live_context_revalidation_flushes_projection_immediately(self, replay):
        with TemporaryDirectory() as folder:
            retained = AcceptedCorrectionRuntime(Path(folder), GENERATION)
            retained.deliver_context_revalidation(
                "context-revalidation:fixture", object(), AUTHORITY)
        replay.assert_called_once_with(retained)


if __name__ == "__main__":
    unittest.main()
