"""A02.2 production staging through the live C07/B13 commit boundary."""
from contextlib import nullcontext
from dataclasses import asdict, replace
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime import admission as factory_admission
from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation, load_bamf_generation_authority,
    read_accepted_vocabulary_registry_export,
    require_issued_a02_staged_vocabulary_extension, stage_vocabulary_extension,
)
from bilqis_mlx.runtime.jit_adoption import (
    _PreparedSuccessorRuntime, _accepted_lease_run_identity,
    _publish_native_staged_candidate,
)
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease
from bilqis_mlx.runtime.tests.custody.bamf_bundle.vocabulary import (
    test_production_staging as production_staging_support,
)
from bilqis_mlx.runtime.tests.operator.test_admission import _executable_fixture


DISPOSABLE_AVAILABLE_BYTES = 1 << 50


def _digest(value) -> str:
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def _bank_zero_digests(student) -> tuple[str, str, str]:
    optimizer = student.retained_state.optimizer
    name = "identity.bank.0"
    return (
        _digest(optimizer.parameters[name]),
        _digest(optimizer.m[name]),
        _digest(optimizer.v[name]),
    )


@unittest.skipUnless(
    os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
    "full A02 -> C07/B13 witness is explicitly gated",
)
class A02C07ProductionAdoptionTests(unittest.TestCase):
    _publish_source_parent = (
        production_staging_support.A02ProductionStagingTests._publish_source_parent)
    _source_patches = (
        production_staging_support.A02ProductionStagingTests._source_patches)

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.pointer = self.run / "bamf-state.json"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()
        close_data_planes()

    def tearDown(self):
        close_data_planes()
        self.environment.stop()
        self.temporary.cleanup()

    def _stage_real_successor(self, snapshot):
        with self._source_patches(snapshot), patch(
                "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission.shutil.disk_usage",
                return_value=SimpleNamespace(free=DISPOSABLE_AVAILABLE_BYTES)):
            staged = stage_vocabulary_extension(
                self.run, "/artifact", Path("/source"), ("urn:concept:8192",))
        self.assertIs(require_issued_a02_staged_vocabulary_extension(staged), staged)
        return staged

    def _c07_inputs(self, parent):
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release

        current, graph = _executable_fixture(seed=17)
        successor, successor_graph = _executable_fixture(seed=18)
        self.assertEqual(successor_graph, graph)
        factory_admission._persist_executable_factory_release(self.run, current)
        origin = Checkpoint("7" * 64, "bundles/foundation-origin", 0, True)
        program = schedule_program_from_executable_release(current)
        runtime = _PreparedSuccessorRuntime(
            None, self.run, {"school": asdict(start_new(program, origin))},
            None, None, graph, object(), object(), 0.)
        lease = replace(
            _lease(), run_identity=_accepted_lease_run_identity(parent.run_identity))
        return (
            current, successor, origin, runtime, lease,
            SimpleNamespace(successor=successor),
            SimpleNamespace(proposal_sha256="7" * 64),
        )

    def _publish(self, snapshot, staged, inputs, *, crash=False):
        current, _successor, origin, runtime, lease, selected, proposal = inputs
        publication = patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._atomic_pointer",
            side_effect=RuntimeError("A02 crash before pointer publication"),
        ) if crash else nullcontext()
        with patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease",
                return_value=lease), self._source_patches(snapshot), \
                patch(
                    "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission.shutil.disk_usage",
                    return_value=SimpleNamespace(free=DISPOSABLE_AVAILABLE_BYTES)), \
                patch.object(mlx_checkpoint, "assert_headroom"), publication:
            return _publish_native_staged_candidate(
                runtime, selected, proposal, staged, lease, object(),
                current=current, checkpoint=origin)

    def test_real_a02_staging_crash_then_c07_commit_preserves_parent_neural_state(self):
        snapshot, _features, _optimizer = self._publish_source_parent()
        parent, _manifest = load_bamf_generation_authority(self.pointer)
        before = _bank_zero_digests(parent)
        staged = self._stage_real_successor(snapshot)
        inputs = self._c07_inputs(parent)
        current, successor = inputs[:2]

        with self.assertRaisesRegex(RuntimeError, "A02 crash before pointer publication"):
            self._publish(snapshot, staged, inputs, crash=True)
        after_crash = load_bamf_generation(
            self.pointer, publish_missing_outbox=False)
        bundles_after_crash = tuple(sorted(
            path.name for path in (self.run / "bamf-bundles").iterdir()
            if path.is_dir()))
        self.assertEqual(after_crash.generation, 0)
        self.assertEqual(after_crash.extents.semantic_bank_count, 1)
        self.assertEqual(_bank_zero_digests(after_crash), before)
        self.assertEqual(
            read_accepted_atlas_factory_release(self.run).release_sha256,
            current.release_sha256)

        pointer = self._publish(snapshot, staged, inputs)
        accepted = load_bamf_generation(
            self.pointer, publish_missing_outbox=False)
        bundles_after_retry = tuple(sorted(
            path.name for path in (self.run / "bamf-bundles").iterdir()
            if path.is_dir()))
        self.assertEqual(pointer["generation"], 1)
        self.assertEqual(accepted.extents.semantic_bank_count, 2)
        self.assertEqual(bundles_after_retry, bundles_after_crash)
        self.assertEqual(_bank_zero_digests(accepted), before)
        new_bank = accepted.retained_state.optimizer
        self.assertTrue(np.all(np.asarray(new_bank.m["identity.bank.1"][0]) == 0))
        self.assertTrue(np.all(np.asarray(new_bank.v["identity.bank.1"][0]) == 0))
        export = read_accepted_vocabulary_registry_export(self.run)
        self.assertEqual(export.run_id, accepted.run_id)
        self.assertEqual(export.generation, 1)
        self.assertEqual(export.manifest_sha256, pointer["manifest_sha256"])
        self.assertEqual(
            export.registry_mirror_sha256,
            staged.receipt.registry_mirror_sha256)
        self.assertEqual(export.active_indices, (0, 8192))
        self.assertEqual(
            tuple((row.semantic_id, row.abi_index, row.bank, row.row)
                  for row in export.rows),
            (("urn:concept:8192", 8192, 1, 0),))
        self.assertEqual(export.previous_bank_count, 1)
        self.assertEqual(export.next_bank_count, 2)
        self.assertGreater(export.added_bank_bytes, 0)
        self.assertFalse(export.semantic_authority)
        self.assertFalse(export.training_authorized)
        self.assertEqual(
            read_accepted_atlas_factory_release(self.run).release_sha256,
            successor.release_sha256)


if __name__ == "__main__":
    unittest.main()
