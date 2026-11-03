"""Released-schema pins witnesses."""
from __future__ import annotations
from dataclasses import replace
import json
import os
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.released_frame_schemas import (
    lookup_source_pinned_frame_schema, load_released_frame_schemas,
    seal_released_frame_schemas, verify_source_pinned_frame_schema,
    verify_source_pinned_frame_schema_bytes,
)
from bilqis_mlx.semantics.tests.released_schemas.fixtures import _snapshot


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
        for family in ("micro", "boolean", "numeric"):
            with self.subTest(family=family):
                from bilqis_mlx.semantics.released_frame_schemas import (
                    _load_pinned_released_frame_schemas,
                )
                staged = _load_pinned_released_frame_schemas(
                    family, selection)
                self.assertEqual(len(staged.manifest.bodies), 6)
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
