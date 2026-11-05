"""Released-schema pins witnesses."""
from __future__ import annotations
from dataclasses import replace
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from bilqis_mlx.semantics import released_frame_schemas as public
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.released_frame_schemas import (
    lookup_source_pinned_frame_schema, load_released_frame_schemas,
    seal_released_frame_schemas, verify_source_pinned_frame_schema,
    verify_source_pinned_frame_schema_bytes,
)
from bilqis_mlx.semantics.tests.released_schemas.fixtures import _schema, _snapshot


class ReleasedPinsTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
        "real repo-pinned A01 artifact supplied at source turn-in",
    )
    def test_repo_owned_pins_load_all_actual_source_schema_families(self):
        artifact = os.environ["BILQIS_ATLAS_REAL_ARTIFACT"]
        selection = AtlasArtifactSelection(
            artifact,
            "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7",
            "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306",
            "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec",
        )
        expected_counts = {"micro": 6, "boolean": 6, "evidence": 1, "numeric": 6}
        for family, expected_count in expected_counts.items():
            with self.subTest(family=family):
                from bilqis_mlx.semantics.released_frame_schemas import (
                    _load_pinned_released_frame_schemas,
                )
                staged = _load_pinned_released_frame_schemas(
                    family, selection)
                self.assertEqual(len(staged.manifest.bodies), expected_count)
                if family == "evidence":
                    schema = staged.manifest.bodies[0].parse()
                    self.assertEqual(schema.schema_id, "frame:bravo.evidence.activity/v1")
                    self.assertEqual(
                        tuple(role.role_id for role in schema.roles),
                        ("agent", "category", "status", "reported_duration"),
                    )
                    self.assertEqual(schema.roles[0].allowed_type_ids, ("Entity",))
                for body in staged.manifest.bodies:
                    schema, witness = lookup_source_pinned_frame_schema(
                        body.schema_id, body.revision,
                        source_family=family, atlas_selection=selection)
                    self.assertEqual(witness.schema_body_sha256,
                                     body.schema_body_sha256)
                    self.assertEqual(
                        verify_source_pinned_frame_schema(
                            schema, source_family=family,
                            atlas_selection=selection), schema)
                    with self.assertRaises(BilqisError):
                        verify_source_pinned_frame_schema(
                            replace(schema, scope="caller:forged"),
                            source_family=family, atlas_selection=selection)
                    reordered = json.dumps(
                        dict(reversed(tuple(
                            json.loads(schema.canonical_bytes()).items()))),
                        separators=(",", ":")).encode()
                    self.assertEqual(
                        verify_source_pinned_frame_schema_bytes(
                            reordered, source_family=family,
                            atlas_selection=selection), schema)
                # The EGM attack: caller may self-pin a forged staging
                # manifest, but the production gate re-enters repo pins.
                schema = staged.manifest.bodies[0].parse()
                forged = replace(schema, scope="caller:forged")
                forged_map = SchemaTagMap.from_schemas(
                    staged.manifest.semantic_release, (forged,))
                staging_snapshot = replace(
                    _snapshot(),
                    release_sha256=staged.manifest.semantic_release,
                    bundle_id=staged.manifest.atlas_bundle_id,
                    source_bundle_id=staged.manifest.source_bundle_id)
                forged_manifest = seal_released_frame_schemas(
                    (forged,), forged_map, staging_snapshot)
                self_pinned = load_released_frame_schemas(
                    forged_manifest.canonical_bytes(),
                    expected_sha256=forged_manifest.digest,
                    snapshot=staging_snapshot)
                self.assertEqual(
                    self_pinned.require_schema(
                        forged, self_pinned.lookup(
                            forged.schema_id, forged.revision)),
                    forged)
                with self.assertRaises(BilqisError):
                    verify_source_pinned_frame_schema(
                        forged, source_family=family,
                        atlas_selection=selection)
        with self.assertRaises(BilqisError):
            lookup_source_pinned_frame_schema(
                "frame:missing", 1, source_family="caller:unreleased",
                atlas_selection=selection)
        with self.assertRaises(BilqisError):
            lookup_source_pinned_frame_schema(
                "frame:missing", 1, source_family="micro",
                atlas_selection=replace(
                    selection, release_sha256="0" * 64))


class ReleasedPublicDependencyTests(unittest.TestCase):
    def test_source_loader_reenters_public_manifest_loader(self):
        entry = public._source_pins()[0]
        snapshot = SimpleNamespace(
            release_sha256=entry['semantic_release'],
            bundle_id=entry['atlas_bundle_id'],
            source_bundle_id=entry['source_bundle_id'],
        )
        with patch.object(public, 'load_pinned_atlas_snapshot', return_value=snapshot), \
                patch.object(
                    public, 'load_released_frame_schemas',
                    side_effect=RuntimeError('public manifest loader injected')):
            with self.assertRaisesRegex(
                    RuntimeError, 'public manifest loader injected'):
                public._load_pinned_released_frame_schemas('micro', None)

    def test_source_loader_reenters_public_atlas_loader(self):
        with patch.object(
                public, 'load_pinned_atlas_snapshot',
                side_effect=RuntimeError('public atlas loader injected')):
            with self.assertRaisesRegex(
                    RuntimeError, 'public atlas loader injected'):
                public._load_pinned_released_frame_schemas('micro', None)

    def test_schema_verifier_reenters_public_lookup(self):
        with patch.object(public, 'lookup_source_pinned_frame_schema',
                          side_effect=RuntimeError('public lookup injected')):
            with self.assertRaisesRegex(RuntimeError, 'public lookup injected'):
                public.verify_source_pinned_frame_schema(
                    _schema(), source_family='micro', atlas_selection=None)

    def test_bytes_verifier_reenters_public_verifier(self):
        with patch.object(public, 'verify_source_pinned_frame_schema',
                          side_effect=RuntimeError('public verifier injected')):
            with self.assertRaisesRegex(RuntimeError, 'public verifier injected'):
                public.verify_source_pinned_frame_schema_bytes(
                    _schema().canonical_bytes(), source_family='micro',
                    atlas_selection=None)
