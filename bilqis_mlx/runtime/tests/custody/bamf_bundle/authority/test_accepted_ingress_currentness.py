"""Accepted C09 ingress must recheck generation currentness at mutation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import accepted_corrections
from bilqis_mlx.runtime.accepted_correction_ledger import read_records
from bilqis_mlx.runtime.bamf_bundle.admission import (
    derive_successor_bundle, load_accepted_generation,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, next_accepted_step, parent_state, provision_source_authority_registry,
    publish_candidate, shape_patch, with_source_authority_registry,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY, _event
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef


class AcceptedIngressCurrentnessTests(unittest.TestCase):
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

    def test_pointer_advance_between_validation_and_append_rejects_before_write(self):
        provision_source_authority_registry(self.run, AUTHORITY)
        pointer = self.publish(with_source_authority_registry(
            candidate(parent_state()), AUTHORITY))
        with shape_patch():
            accepted = load_accepted_generation(self.run)
        correction = _event(DependencyRef(DependencyKind.SOURCE, "source:race"))
        entered = Event()
        release = Event()
        original = accepted_corrections.append_current_record

        def paused_append(run_dir, manifest_sha256, record):
            entered.set()
            self.assertTrue(release.wait(5))
            return original(run_dir, manifest_sha256, record)

        successor = derive_successor_bundle(
            accepted,
            next_accepted_step(accepted.retained_state, accepted.extents),
            parent_manifest_sha256=pointer["manifest_sha256"],
            delivery_events=({"event": "FIXTURE_ACCEPTED"},),
        )
        successor = replace(successor, correction_frontier={
            **successor.correction_frontier,
            "source_authority_registry_sha256": AUTHORITY.digest,
            "source_authority_registry": AUTHORITY.to_record(),
        })
        with shape_patch(), patch.object(
                accepted_corrections, "append_current_record",
                side_effect=paused_append), ThreadPoolExecutor(max_workers=1) as pool:
            host = accepted_corrections.AcceptedRuntimeHost(self.run)
            future = pool.submit(
                host.record_correction, correction)
            self.assertTrue(entered.wait(5))
            self.publish(successor)
            release.set()
            with self.assertRaises(BilqisError) as rejected:
                future.result(timeout=5)
        self.assertEqual(
            rejected.exception.context["reason"],
            "BAMF_C09_ACCEPTED_RUNTIME_STALE",
        )
        self.assertEqual(read_records(self.run, pointer["manifest_sha256"]), ())


if __name__ == "__main__":
    unittest.main()
