"""Positive cold read of a bundle emitted by the pinned pre-CAS B13 writer."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import numpy as np

import bilqis_mlx.runtime.bamf_bundle.publication as publication
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.tests.custody.data_plane.base import DataPlaneCase
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state, shape_patch

PRE_CAS = "dfc0c7586c23b6477c08d4db486ade3deeb79fae"
WRITER_SHA256 = "01e66fcbe15802615c3557a2a4b99c0fb75a37d64fe3d61ee30bf56d1301fcdc"


def numerical_observation(student):
    state = student.retained_state
    arrays = {}
    for field in ("parameters", "m", "v", "update_counts"):
        for name, value in getattr(state.optimizer, field).items():
            array = np.asarray(value)
            arrays[field + ":" + name] = [str(array.dtype), list(array.shape),
                                         hashlib.sha256(array.tobytes()).hexdigest()]
    return {"arrays": arrays, "step": state.optimizer_step,
            "policy": state.policy.to_record(), "teacher": dict(student.teacher_state),
            "hyperparameters": json.loads(json.dumps(asdict(student.optimizer_hyperparameters)))}


class PreCasCompatibilityTests(DataPlaneCase):
    def test_pinned_old_writer_bundle_cold_loads_without_rewriting(self):
        repository = Path(__file__).resolve().parents[5]
        source = subprocess.run(
            ["git", "show", PRE_CAS + ":bilqis_mlx/runtime/_custody/bamf_bundle/codec.py"],
            cwd=repository, check=True, capture_output=True).stdout
        self.assertEqual(hashlib.sha256(source).hexdigest(), WRITER_SHA256)
        writer_path = self.root / "pre_cas_codec.py"
        writer_path.write_bytes(source)
        spec = importlib.util.spec_from_file_location(
            "bilqis_mlx.runtime.bamf_bundle.pre_cas_fixture", writer_path)
        writer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(writer)
        run = self.root / "run"
        initial = candidate(parent_state())
        expected = numerical_observation(initial)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(publication, "save_bamf_bundle", side_effect=writer.save_bamf_bundle):
            pointer = publication.publish_bamf_generation(run, initial)
        bundle = run / pointer["bundle"]
        before = {path.name: path.read_bytes() for path in bundle.iterdir()}
        manifest = json.loads(before["manifest.json"])
        self.assertNotIn("object_sha256", manifest["tensors"])
        self.assertIn(manifest["tensors"]["filename"], before)
        with shape_patch():
            self.assertEqual(numerical_observation(writer.load_bamf_bundle(bundle)), expected)
            self.assertEqual(numerical_observation(load_bamf_generation(run / "bamf-state.json")), expected)
        script = "\n".join((
            "import json,sys",
            "from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation",
            "from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch",
            "from bilqis_mlx.runtime.tests.custody.bamf_bundle.test_pre_cas_compatibility import numerical_observation",
            "with shape_patch(): student=load_bamf_generation(sys.argv[1],publish_missing_outbox=False)",
            "print(json.dumps(numerical_observation(student),sort_keys=True))",
        ))
        result = subprocess.run([sys.executable, "-c", script, str(run / "bamf-state.json")],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), expected)
        self.assertEqual({path.name: path.read_bytes() for path in bundle.iterdir()}, before)
