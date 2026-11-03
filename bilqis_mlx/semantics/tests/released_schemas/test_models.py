"""Released-schema model identity and exact body witnesses."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import pickle
import unittest
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics import released_frame_schemas
from bilqis_mlx.semantics.tests.released_schemas.fixtures import RELEASE, _release


class ReleasedModelIdentityTests(TestCase):
    def test_verified_manifest_body_and_witness_keep_pickle_identity(self):
        schema, _, _, _, verified = _release()
        witness = verified.lookup(schema.schema_id, schema.revision)
        for value in (verified, verified.manifest, verified.manifest.bodies[0], witness):
            with self.subTest(record=type(value).__name__):
                self.assertEqual(
                    type(value).__module__, released_frame_schemas.__name__)
                restored = pickle.loads(pickle.dumps(value))
                self.assertIs(type(restored), type(value))
                self.assertEqual(restored, value)


class ReleasedModelsTests(unittest.TestCase):
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
