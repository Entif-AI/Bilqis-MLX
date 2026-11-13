"""B13 cold-load ownership and safe tensor entry boundaries."""
import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx
import bilqis_mlx.runtime.bamf_bundle.codec as codec
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle, save_bamf_bundle
from bilqis_mlx.runtime.bamf_bundle.publication.authority import validate_parent_transition
from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.runtime.checkpoint_outbox import with_delivery_outbox
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state, shape_patch


class CodecBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {'BILQIS_DATA_PLANE': str(self.root / 'plane.db')})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def save(self, root):
        with shape_patch(), patch.object(mlx_checkpoint, 'assert_headroom'):
            return save_bamf_bundle(candidate(parent_state()), root)

    def rehash_outbox(self, root, outbox):
        raw = canonical(outbox)
        digest = sha(raw)
        data_plane().put_object(digest, raw)
        (root / 'outbox.json').write_bytes(raw)
        path = root / 'manifest.json'
        manifest = json.loads(path.read_bytes())
        manifest['sidecars']['outbox'].update(sha256=digest, object_sha256=digest)
        raw = canonical(manifest)
        data_plane().put_node(sha(raw), raw, manifest['generation'], manifest['parent_manifest_sha256'])
        path.write_bytes(raw)

    def test_rehashed_outbox_must_belong_to_this_generation_before_tensor_load(self):
        for kind in ('empty', 'wrong-id', 'other-generation'):
            with self.subTest(kind=kind):
                root = self.root / kind
                self.save(root)
                current = json.loads((root / 'outbox.json').read_bytes())
                invalid = [] if kind == 'empty' else [{**current[0], 'event_id': '0' * 64}]
                if kind == 'other-generation':
                    payload = {k: v for k, v in current[0].items() if k != 'event_id'}
                    invalid = with_delivery_outbox({'run_id': 'fixture-run', 'generation': 1},
                                                   [payload])['delivery_outbox']
                self.rehash_outbox(root, invalid)
                with patch.object(codec._mlx_checkpoint, 'load_bamf_state_payload',
                                  side_effect=AssertionError('unsafe tensor construction reached')):
                    with self.assertRaises(BilqisError):
                        load_bamf_bundle(root)

    def test_matching_external_legacy_tensor_symlink_rejects_before_mlx_load(self):
        root = self.root / 'linked'
        saved = self.save(root)
        manifest_path = root / 'manifest.json'
        manifest = json.loads(manifest_path.read_bytes())
        canonical_tensor = data_plane().require_file_object(saved['tensors']['sha256'])
        tensor = root / 'bamf-state.safetensors'
        external = self.root / 'outside.safetensors'
        external.write_bytes(canonical_tensor.read_bytes())
        tensor.symlink_to(external)
        manifest['tensors'].pop('object_sha256')
        raw = canonical(manifest)
        data_plane().put_node(
            sha(raw), raw, manifest['generation'], manifest['parent_manifest_sha256'])
        manifest_path.write_bytes(raw)
        with patch.object(mx, 'load', side_effect=AssertionError('unsafe MLX load reached')):
            with self.assertRaises(BilqisError):
                load_bamf_bundle(root)

    def test_invalid_generation_identity_rejects_before_creating_bundle(self):
        original = candidate(parent_state())
        invalid = (
            replace(original, run_id=123),
            replace(original, parent_manifest_sha256='a' * 64),
            replace(original, generation=-1, parent_manifest_sha256='a' * 64,
                    transition={**original.transition, 'kind': 'RETAINED_CANDIDATE'}),
        )
        for index, value in enumerate(invalid):
            root = self.root / str(index)
            with self.subTest(index=index), patch.object(codec._mlx_checkpoint, 'save_bamf_state_payload',
                    side_effect=AssertionError('unsafe tensor write reached')):
                with self.assertRaises(BilqisError):
                    save_bamf_bundle(value, root)
                self.assertFalse(root.exists())

    def test_retained_candidate_cannot_downgrade_allocation_metadata_change(self):
        original = parent_state().allocations
        changed = MotifAllocationSnapshot(
            original.manifest,
            observed_uses=(("0" * 64, 1),))
        topology = SimpleNamespace(digest="1" * 64)
        extents = SimpleNamespace(
            digest="2" * 64, motif_page_count=1,
            motif_key_map_digest=original.manifest.digest)
        parent = SimpleNamespace(
            run_id="fixture-run", generation=0, parent_manifest_sha256=None,
            topology=topology, extents=extents,
            retained_state=SimpleNamespace(optimizer_step=11, allocations=original))
        child = SimpleNamespace(
            run_id="fixture-run", generation=1, parent_manifest_sha256="6" * 64,
            topology=topology, extents=extents,
            retained_state=SimpleNamespace(optimizer_step=12, allocations=changed),
            transition={"schema": "bilqis.mlx.bamf-generation-transition/v1",
                        "kind": "RETAINED_CANDIDATE",
                        "invalidate_derived_caches": True})
        pointer = {
            "run_id": child.run_id, "generation": 0,
            "manifest_sha256": "6" * 64,
            "parent_manifest_sha256": parent.parent_manifest_sha256,
            "bundle": "parent",
        }
        with self.assertRaises(BilqisError):
            validate_parent_transition(
                self.root, pointer, child, load_bundle=lambda *_a, **_k: parent,
                reconcile=lambda *_a, **_k: None)
