"""B13 storage envelopes reject incomplete identity custody before tensor I/O."""
import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.bamf_bundle.codec as codec
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle, save_bamf_bundle
from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha
from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state, shape_patch

SCHEMAS = {
    'semantic_abi': 'bilqis.mlx.bamf-semantic-abi/v1',
    'compiler_features': 'bilqis.mlx.bamf-compiler-features/v1',
    'correction_frontier': 'bilqis.mlx.bamf-correction-frontier/v1',
    'teacher_state': 'bilqis.mlx.bamf-teacher-state/v1',
    'evaluation_contract': 'bilqis.mlx.bamf-evaluation-contract/v1',
}


def source():
    value = candidate(parent_state())
    return replace(value, **{name: {**getattr(value, name), 'schema': schema}
                             for name, schema in SCHEMAS.items()})


class SidecarContractTests(unittest.TestCase):
    def assertHeldBeforeTensorSave(self, value):
        with TemporaryDirectory() as tmp:
            with patch.object(codec._mlx_checkpoint, 'save_bamf_state_payload',
                              side_effect=AssertionError('unsafe tensor write reached')):
                with self.assertRaises(BilqisError):
                    save_bamf_bundle(value, Path(tmp) / 'bundle')

    def test_every_identity_sidecar_requires_its_version(self):
        value = source()
        for name in SCHEMAS:
            for schema in (None, 'unsupported/v9'):
                raw = dict(getattr(value, name))
                if schema is None:
                    raw.pop('schema')
                else:
                    raw['schema'] = schema
                with self.subTest(name=name, schema=schema):
                    self.assertHeldBeforeTensorSave(replace(value, **{name: raw}))

    def test_compiler_and_bank_identities_are_required(self):
        value = source()
        for name, field, variants in (
            ('semantic_abi', 'bank_identities', (None, [], ['',], ['bank:0', 'bank:0'], [False])),
            ('compiler_features', 'compiler_sha256', (None, 'missing', 'A' * 64)),
            ('correction_frontier', 'frontier', (None, 'not a frontier')),
        ):
            for replacement in variants:
                raw = dict(getattr(value, name))
                if replacement is None:
                    raw.pop(field)
                else:
                    raw[field] = replacement
                with self.subTest(name=name, field=field, replacement=replacement):
                    self.assertHeldBeforeTensorSave(replace(value, **{name: raw}))

    def test_boolean_or_negative_epochs_are_not_integer_identity(self):
        original = source()
        value = replace(original,
            compiler_features={**original.compiler_features, 'rights_epoch': 0, 'correction_generation': 0},
            correction_frontier={**original.correction_frontier, 'rights_epoch': 0, 'correction_generation': 0},
            teacher_state={**original.teacher_state, 'teacher_epoch': 0},
            provenance=replace(original.provenance, teacher_epoch=0))
        for name, field in (('compiler_features', 'rights_epoch'),
                            ('compiler_features', 'correction_generation'),
                            ('correction_frontier', 'rights_epoch'),
                            ('correction_frontier', 'correction_generation'),
                            ('teacher_state', 'teacher_epoch')):
            for replacement in (False, -1):
                raw = {**getattr(value, name), field: replacement}
                with self.subTest(name=name, field=field, replacement=replacement):
                    self.assertHeldBeforeTensorSave(replace(value, **{name: raw}))

    def test_rehashed_incomplete_compiler_rejects_before_tensor_load(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {'BILQIS_DATA_PLANE': tmp + '/plane.db'}):
            root = Path(tmp) / 'bundle'
            with shape_patch(), patch.object(mlx_checkpoint, 'assert_headroom'):
                save_bamf_bundle(source(), root)
            sidecar = root / 'compiler-features.json'
            record = json.loads(sidecar.read_bytes())
            record.pop('compiler_sha256')
            raw = canonical(record)
            digest = sha(raw)
            data_plane().put_object(digest, raw)
            sidecar.write_bytes(raw)
            manifest_path = root / 'manifest.json'
            manifest = json.loads(manifest_path.read_bytes())
            manifest['sidecars']['compiler_features'].update(sha256=digest, object_sha256=digest)
            manifest_raw = canonical(manifest)
            data_plane().put_node(sha(manifest_raw), manifest_raw,
                                  manifest["generation"], manifest["parent_manifest_sha256"])
            manifest_path.write_bytes(manifest_raw)
            with patch.object(codec._mlx_checkpoint, 'load_bamf_state_payload',
                              side_effect=AssertionError('unsafe tensor construction reached')):
                with self.assertRaises(BilqisError):
                    load_bamf_bundle(root)
