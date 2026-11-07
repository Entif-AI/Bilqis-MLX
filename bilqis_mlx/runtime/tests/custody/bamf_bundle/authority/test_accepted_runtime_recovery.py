"""Accepted C09 ledger crash/concurrency recovery witnesses."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.tests.test_frame_encoder import FrameEncoderTests
from bilqis_mlx.runtime.accepted_correction_ledger import (
    append_record, correction_record, read_records,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_execution_cache, derive_successor_bundle, load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle.execution_cache import bind_motif_artifact_owner
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, next_accepted_step, parent_state, publish_candidate, shape_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import _event, _sign_event


class AcceptedRuntimeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_candidate(self.run, source)

    def _motif_fixture(self):
        self.publish(candidate(parent_state()))
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
        fixture = FrameEncoderTests()
        fixture.setUp()
        compiled, _vectors, _ast = fixture.compiled_inputs()
        compiled = replace(
            compiled,
            extents=replace(
                compiled.extents,
                motif_key_map_digest=cache.motif_manifest.digest,
            ),
        )
        return cache, compiled, bind_motif_artifact_owner(cache, compiled)

    def test_file_ahead_of_history_after_commit_crash_recovers_exact_history(self):
        cache, _compiled, owner = self._motif_fixture()
        first = _event(owner.source_dependencies[0])
        second = _sign_event(replace(
            first, event_id="correction:synthetic:crash-recovery-2",
            source_receipt_sha256="e" * 64, new_evidence_sha256="d" * 64))
        manifest = cache.accepted_manifest_sha256
        first_record = correction_record(manifest, first)
        second_record = correction_record(manifest, second)
        append_record(self.run, manifest, first_record)
        with patch(
                "bilqis_mlx.runtime.accepted_correction_storage.commit_history",
                side_effect=RuntimeError("simulated crash after ledger fsync")):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                append_record(self.run, manifest, second_record)
        recovered = read_records(self.run, manifest)
        self.assertEqual(
            tuple(item["event_id"] for item in recovered),
            (first_record["event_id"], second_record["event_id"]))

    def test_ancestor_commit_crash_recovers_after_successor_append(self):
        cache, _compiled, owner = self._motif_fixture()
        first = _event(owner.source_dependencies[0])
        second = _sign_event(replace(
            first, event_id="correction:synthetic:ancestor-crash-2",
            source_receipt_sha256="e" * 64, new_evidence_sha256="d" * 64))
        successor_event = _sign_event(replace(
            first, event_id="correction:synthetic:successor-3",
            source_receipt_sha256="c" * 64, new_evidence_sha256="b" * 64))
        ancestor_manifest = cache.accepted_manifest_sha256
        first_record = correction_record(ancestor_manifest, first)
        second_record = correction_record(ancestor_manifest, second)
        append_record(self.run, ancestor_manifest, first_record)
        with patch(
                "bilqis_mlx.runtime.accepted_correction_storage.commit_history",
                side_effect=RuntimeError("simulated ancestor crash after ledger fsync")):
            with self.assertRaisesRegex(RuntimeError, "simulated ancestor crash"):
                append_record(self.run, ancestor_manifest, second_record)
        with shape_patch():
            parent = load_accepted_generation(self.run)
        retained = next_accepted_step(parent.retained_state)
        successor = derive_successor_bundle(
            parent, retained, parent_manifest_sha256=ancestor_manifest,
            delivery_events=({"event": "FIXTURE_SUCCESSOR"},))
        published = self.publish(successor)
        successor_manifest = published["manifest_sha256"]
        successor_record = correction_record(successor_manifest, successor_event)
        append_record(self.run, successor_manifest, successor_record)
        recovered = read_records(self.run, successor_manifest)
        self.assertEqual(
            tuple(item["event_id"] for item in recovered),
            (first_record["event_id"], second_record["event_id"],
             successor_record["event_id"]))

    def test_ancestor_recovery_rejects_foreign_manifest_suffix(self):
        cache, _compiled, owner = self._motif_fixture()
        first = _event(owner.source_dependencies[0])
        second = _sign_event(replace(
            first, event_id="correction:synthetic:ancestor-foreign-2",
            source_receipt_sha256="e" * 64, new_evidence_sha256="d" * 64))
        foreign = _sign_event(replace(
            first, event_id="correction:synthetic:foreign-manifest-3",
            source_receipt_sha256="c" * 64, new_evidence_sha256="b" * 64))
        ancestor_manifest = cache.accepted_manifest_sha256
        append_record(self.run, ancestor_manifest, correction_record(ancestor_manifest, first))
        with patch(
                "bilqis_mlx.runtime.accepted_correction_storage.commit_history",
                side_effect=RuntimeError("simulated ancestor crash after ledger fsync")):
            with self.assertRaisesRegex(RuntimeError, "simulated ancestor crash"):
                append_record(self.run, ancestor_manifest,
                              correction_record(ancestor_manifest, second))
        from bilqis_mlx.runtime.accepted_correction_records import _canonical
        from bilqis_mlx.runtime.accepted_correction_storage import ledger_path
        foreign_record = correction_record("f" * 64, foreign)
        with ledger_path(self.run).open("ab") as stream:
            stream.write(_canonical(foreign_record) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        with self.assertRaises(BilqisError) as caught:
            read_records(self.run, ancestor_manifest)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")

    def test_concurrent_process_writers_commit_one_exact_history(self):
        cache, _compiled, owner = self._motif_fixture()
        first = _event(owner.source_dependencies[0])
        second = _sign_event(replace(
            first, event_id="correction:synthetic:process-writer-2",
            source_receipt_sha256="e" * 64, new_evidence_sha256="d" * 64))
        manifest = cache.accepted_manifest_sha256
        records = (correction_record(manifest, first), correction_record(manifest, second))
        barrier = self.root / "writers.start"
        script = (
            "import json, pathlib, sys, time; "
            "from bilqis_mlx.runtime.accepted_correction_ledger import append_record; "
            "run=pathlib.Path(sys.argv[1]); manifest=sys.argv[2]; "
            "record=json.loads(sys.argv[3]); barrier=pathlib.Path(sys.argv[4]); "
            "deadline=time.monotonic()+10; "
            "\nwhile not barrier.exists():\n"
            "    if time.monotonic() >= deadline: raise RuntimeError('barrier timeout')\n"
            "    time.sleep(0.001)\n"
            "append_record(run, manifest, record)")
        processes = [subprocess.Popen(
            [sys.executable, "-c", script, str(self.run), manifest,
             json.dumps(record, sort_keys=True), str(barrier)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=os.environ.copy()) for record in records]
        barrier.touch()
        outputs = [process.communicate(timeout=15) for process in processes]
        for process, (stdout, stderr) in zip(processes, outputs):
            self.assertEqual(process.returncode, 0,
                             msg=f"stdout={stdout!r} stderr={stderr!r}")
        recovered = read_records(self.run, manifest)
        self.assertEqual(len(recovered), 2)
        self.assertEqual({item["event_id"] for item in recovered},
                         {record["event_id"] for record in records})


if __name__ == "__main__":
    unittest.main()
