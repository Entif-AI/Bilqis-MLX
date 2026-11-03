"""A03.4 released schema bodies must be checked against a pinned source artifact."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.semantics.atlas_projection import AbiEntry
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_projection import (
    AtlasCounts, FrozenAtlasSnapshot,
)
from bilqis_mlx.semantics.frame_adapters import (
    _schema_for_symbol, bind_registered_source_row,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import (
    lookup_source_pinned_frame_schema,
    load_released_frame_schemas, persist_released_frame_schemas,
    seal_released_frame_schemas, verify_source_pinned_frame_schema,
    verify_source_pinned_frame_schema_bytes,
)
from bilqis_mlx.source_adapters.school import A_ORACLE, live_source_registry
from bilqis_mlx.source_adapters.structure import inspect_source_query


from bilqis_mlx.semantics.tests.released_schemas.fixtures import (
    RELEASE, _snapshot, _schema, _release,
)


class ReleasedVerificationTests(unittest.TestCase):
    def test_pinned_release_verifies_exact_schema_and_witness(self):
        schema, tag_map, payload, digest, verified = _release()
        witness = verified.lookup(schema.schema_id, schema.revision)
        self.assertEqual(witness.semantic_release, RELEASE)
        self.assertEqual(witness.schema_map_sha256, tag_map.digest)
        self.assertEqual(witness.release_manifest_sha256, digest)
        self.assertEqual(
            witness.schema_body_sha256,
            hashlib.sha256(schema.canonical_bytes()).hexdigest())
        self.assertEqual(verified.require_schema(schema, witness), schema)
        self.assertEqual(
            verified.canonical_bytes(), payload)


    def test_same_id_revision_cannot_substitute_any_semantic_body(self):
        schema, _, _, _, verified = _release()
        witness = verified.lookup(schema.schema_id, schema.revision)
        mutants = (
            replace(schema, ast_construct="source:relation"),
            replace(schema, roles=tuple(reversed(schema.roles))),
            replace(schema, roles=(
                replace(schema.roles[0], allowed_type_ids=("Number",)),
                schema.roles[1])),
            replace(schema, roles=(
                schema.roles[0],
                replace(schema.roles[1], max_cardinality=3))),
            replace(schema, scope="foreign"),
            replace(schema, order_mode="UNORDERED"),
            replace(schema, ast_contract_sha256="8" * 64),
        )
        for candidate in mutants:
            with self.subTest(candidate=candidate):
                with self.assertRaises(BilqisError) as caught:
                    verified.require_schema(candidate, witness)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "FRAME_RELEASED_SCHEMA_BODY_MISMATCH")


    def test_forged_local_catalog_cannot_replace_pinned_source_release(self):
        schema, _, _, digest, _ = _release()
        forged = replace(schema, scope="forged")
        forged_map = SchemaTagMap.from_schemas(RELEASE, (forged,))
        forged_payload = seal_released_frame_schemas(
            (forged,), forged_map, _snapshot()).canonical_bytes()
        with self.assertRaises(BilqisError) as caught:
            load_released_frame_schemas(
                forged_payload, expected_sha256=digest,
                snapshot=_snapshot(),
                expected_semantic_release=RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_RELEASED_MANIFEST_DIGEST_MISMATCH")


    def test_foreign_release_and_map_identity_reject_before_lookup(self):
        _, tag_map, payload, digest, _ = _release()
        for args in (
            {"expected_semantic_release": "f" * 64},
            {"expected_schema_map_sha256": "0" * 64},
        ):
            with self.subTest(args=args):
                with self.assertRaises(BilqisError):
                    load_released_frame_schemas(
                        payload, expected_sha256=digest,
                        snapshot=_snapshot(), **args)
        with self.assertRaises(BilqisError):
            seal_released_frame_schemas(
                (_schema(),), SchemaTagMap.from_schemas(
                    "f" * 64, (_schema(),)), _snapshot())
        self.assertEqual(tag_map.semantic_release, RELEASE)


    def test_reordered_json_keys_canonicalize_but_role_reorder_does_not(self):
        schema, _, _, _, verified = _release()
        witness = verified.lookup(schema.schema_id, schema.revision)
        raw = json.loads(schema.canonical_bytes())
        reordered = json.dumps(
            dict(reversed(tuple(raw.items()))),
            separators=(",", ":")).encode()
        self.assertEqual(
            verified.require_schema_bytes(reordered, witness), schema)
        raw["roles"] = list(reversed(raw["roles"]))
        with self.assertRaises(BilqisError):
            verified.require_schema_bytes(
                json.dumps(raw).encode(), witness)


    def test_missing_trusted_digest_and_noncanonical_manifest_fail_closed(self):
        _, _, payload, digest, _ = _release()
        with self.assertRaises(BilqisError):
            load_released_frame_schemas(
                payload, expected_sha256=None, snapshot=_snapshot())
        altered = json.dumps(
            json.loads(payload), indent=2).encode()
        with self.assertRaises(BilqisError):
            load_released_frame_schemas(
                altered, expected_sha256=hashlib.sha256(altered).hexdigest(),
                snapshot=_snapshot())
        self.assertEqual(len(digest), 64)
