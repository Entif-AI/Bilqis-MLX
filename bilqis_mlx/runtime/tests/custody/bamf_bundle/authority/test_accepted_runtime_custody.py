"""Accepted-generation runtime custody and C09 replay witnesses."""
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
from bilqis_mlx.runtime.accepted_corrections import (
    _RUNTIME_OWNER, record_accepted_correction,
)
from bilqis_mlx.runtime.accepted_correction_ledger import (
    append_record, correction_record, read_records,
)
from bilqis_mlx.runtime.atlas_cache_codec import CacheAuthorityRuntime
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.runtime.bamf_bundle import admission, publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import (
    admit_candidate_step, bind_accepted_cache_authority,
    bind_accepted_correction_authority, bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
    AcceptedExecutionCache, bind_motif_artifact_owner,
    require_accepted_execution_cache,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _sign_event,
)


class AcceptedRuntimeCustodyTests(unittest.TestCase):
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
            return publish_bamf_generation(
                self.run, source, acceptance=acceptance(source))

    def test_only_accepted_b13_custody_mints_live_execution_cache(self):
        self.publish(candidate(parent_state()))
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            rebound = bind_accepted_execution_cache(self.run)
        self.assertIs(require_accepted_execution_cache(cache), cache)
        self.assertIs(rebound, cache)
        self.assertEqual(cache.run_id, "fixture-run")
        self.assertEqual(
            cache.motif_manifest.digest,
            parent_state().allocations.manifest.digest,
        )
        with self.assertRaises(BilqisError):
            AcceptedExecutionCache()

    def test_accepted_b13_custody_issues_and_retains_opaque_cache_authority(self):
        self.publish(candidate(parent_state()))
        registry = SourceAuthorityRegistry((SourceAuthorityKey(
            "cache-host", "1" * 64,
            (SourceAuthorityScope(DependencyKind.ARTIFACT, "cache:"),),
        ),))
        source = lambda: object()
        with shape_patch():
            cache, authority = bind_accepted_cache_authority(
                self.run, registry, source)
            rebound_cache, rebound_authority = bind_accepted_cache_authority(
                self.run, registry, source)
        self.assertIsInstance(authority, CacheAuthorityRuntime)
        self.assertIs(rebound_cache, cache)
        self.assertIs(rebound_authority, authority)
        with shape_patch(), self.assertRaises(BilqisError):
            bind_accepted_cache_authority(
                self.run, registry, lambda: object())

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

    def test_signed_accepted_correction_replays_into_motif_owner_after_cold_restart(self):
        cache, compiled, owner = self._motif_fixture()
        correction = _event(owner.source_dependencies[0])
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
        self.assertTrue(owner.queue.held_artifact_ids)
        with self.assertRaises(BilqisError):
            owner.require(cache, compiled)

        admission._EXECUTION_CACHE_OWNER.entries.clear()
        _RUNTIME_OWNER.clear()
        with shape_patch():
            cold_cache = bind_accepted_correction_authority(
                self.run, AUTHORITY)
        with self.assertRaises(BilqisError):
            bind_motif_artifact_owner(cold_cache, compiled)
        with self.assertRaises(BilqisError):
            bind_motif_artifact_owner(cold_cache, compiled)

    def test_missing_local_correction_ledger_fails_closed_after_history_exists(self):
        _cache, compiled, owner = self._motif_fixture()
        correction = _event(owner.source_dependencies[0])
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
        (self.run / "events.jsonl").unlink()
        admission._EXECUTION_CACHE_OWNER.entries.clear()
        _RUNTIME_OWNER.clear()
        with shape_patch():
            cold_cache = bind_accepted_correction_authority(
                self.run, AUTHORITY)
        with self.assertRaises(BilqisError) as caught:
            bind_motif_artifact_owner(cold_cache, compiled)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_CORRECTION_LEDGER_MISSING",
        )

    def test_truncated_local_correction_ledger_fails_closed_against_committed_history(self):
        _cache, compiled, owner = self._motif_fixture()
        first = _event(owner.source_dependencies[0])
        second = _sign_event(replace(
            first,
            event_id="correction:synthetic:history-2",
            source_receipt_sha256="e" * 64,
            new_evidence_sha256="d" * 64,
        ))
        with shape_patch():
            record_accepted_correction(self.run, first, AUTHORITY)
            record_accepted_correction(self.run, second, AUTHORITY)
        ledger = self.run / "events.jsonl"
        lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
        ledger.write_text("".join(lines[:-1]), encoding="utf-8")
        admission._EXECUTION_CACHE_OWNER.entries.clear()
        _RUNTIME_OWNER.clear()
        with shape_patch():
            cold_cache = bind_accepted_correction_authority(self.run, AUTHORITY)
        with self.assertRaises(BilqisError) as caught:
            bind_motif_artifact_owner(cold_cache, compiled)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT",
        )

    def test_file_ahead_of_history_after_commit_crash_recovers_exact_history(self):
        cache, _compiled, owner = self._motif_fixture()
        first = _event(owner.source_dependencies[0])
        second = _sign_event(replace(
            first,
            event_id="correction:synthetic:crash-recovery-2",
            source_receipt_sha256="e" * 64,
            new_evidence_sha256="d" * 64,
        ))
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
            (first_record["event_id"], second_record["event_id"]),
        )

    def test_concurrent_process_writers_commit_one_exact_history(self):
        cache, _compiled, owner = self._motif_fixture()
        first = _event(owner.source_dependencies[0])
        second = _sign_event(replace(
            first,
            event_id="correction:synthetic:process-writer-2",
            source_receipt_sha256="e" * 64,
            new_evidence_sha256="d" * 64,
        ))
        manifest = cache.accepted_manifest_sha256
        records = (
            correction_record(manifest, first),
            correction_record(manifest, second),
        )
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
            "append_record(run, manifest, record)"
        )
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", script, str(self.run), manifest,
                 json.dumps(record, sort_keys=True), str(barrier)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=os.environ.copy(),
            )
            for record in records
        ]
        barrier.touch()
        outputs = [process.communicate(timeout=15) for process in processes]
        for process, (stdout, stderr) in zip(processes, outputs):
            self.assertEqual(
                process.returncode, 0,
                msg=f"stdout={stdout!r} stderr={stderr!r}",
            )

        recovered = read_records(self.run, manifest)
        self.assertEqual(len(recovered), 2)
        self.assertEqual(
            {item["event_id"] for item in recovered},
            {record["event_id"] for record in records},
        )

    def test_production_step_reaches_the_owner_binder(self):
        self.publish(candidate(parent_state()))
        with shape_patch(), patch.object(
                admission, "production_candidate_step",
                side_effect=admission.production_candidate_step) as step:
            with self.assertRaises(BilqisError):
                admit_candidate_step(
                    self.run, {}, loss_bearing_target=True,
                    teacher_hparams=None, max_norm=1.)
        self.assertTrue(step.called)

    def test_no_loss_step_cannot_promote_census_to_execution(self):
        self.publish(candidate(parent_state()))
        marker = object()
        with shape_patch(), patch.object(
                admission, "production_candidate_step", return_value=marker) as step:
            result = admit_candidate_step(
                self.run, {}, loss_bearing_target=False,
                teacher_hparams=None, max_norm=1.)
        self.assertIs(result, marker)
        for forbidden in ("motif_reads", "executed_parameter_names",
                          "visible_identity_rows", "feedback_identity_rows",
                          "local_slot_rows"):
            self.assertNotIn(forbidden, step.call_args.kwargs)

    def test_admission_forwards_b11_gradient_execution_without_rederiving_it(self):
        self.publish(candidate(parent_state()))
        owner_execution = object()
        marker = object()
        with shape_patch(), patch.object(
                admission, "production_candidate_step", return_value=marker) as step:
            result = admit_candidate_step(
                self.run, loss_bearing_target=True,
                gradient_execution=owner_execution, teacher_hparams=None,
                max_norm=1.)
        self.assertIs(result, marker)
        self.assertIs(step.call_args.kwargs["gradient_execution"], owner_execution)
        self.assertIsNone(step.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
