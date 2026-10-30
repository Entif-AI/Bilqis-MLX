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


RELEASE = "a" * 64


def _snapshot():
    return FrozenAtlasSnapshot(
        schema="bilqis.semantic-atlas-snapshot/v1",
        bundle_id="b" * 64,
        release_sha256=RELEASE,
        source_bundle_id="c" * 64,
        canonical_rdf_sha256="d" * 64,
        coverage_sha256="e" * 64,
        source_rows_sha256="f" * 64,
        conformance_sha256="1" * 64,
        prior_abi_sha256="2" * 64,
        shape_policy_sha256="3" * 64,
        active_set_sha256="4" * 64,
        counts=AtlasCounts(1, 1, 1, 0, 0, 0, 0, 0, 0, 0),
        formal_domain_bindings=(), abi_entries=(), concepts=(),
        relations=(), withheld_rows=(), semantic_lookup=(),
        concept_lookup=(),
    )


def _schema():
    return FrameSchema(
        "frame:source.op", 1, "source:apply",
        (RoleSpec("agent", ("Entity",), 1, 1),
         RoleSpec("theme", ("Entity",), 0, 2)),
        "ORDERED", "source-query", ast_contract_sha256="9" * 64,
    )


def _release():
    schema = _schema()
    tag_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
    staged = seal_released_frame_schemas(
        (schema,), tag_map, _snapshot())
    payload = staged.canonical_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    verified = load_released_frame_schemas(
        payload, expected_sha256=digest,
        snapshot=_snapshot(),
        expected_semantic_release=RELEASE,
        expected_schema_map_sha256=tag_map.digest,
    )
    return schema, tag_map, payload, digest, verified


class ReleasedFrameSchemaTests(unittest.TestCase):
    def test_real_registered_a_source_schema_can_be_published_and_verified(self):
        root = Path(__file__).resolve().parents[4]
        source_root = root / "vendor/legacy-v16"
        graph = read_sources(source_root)[2]
        registry = live_source_registry()
        adapter = registry.require(
            "bilqis_mlx.grade_a_probe.make_record", A_ORACLE)
        row = adapter.draw(
            source_root=source_root, graph=graph, course=None,
            capability="A.IDENTITY", seed=31, each=2)[0]
        abi_rows = json.loads(
            (root / "bilqis_mlx/semantics/copular_registry_v1.json").read_text()
        )["rows"][1:]
        entries = tuple(AbiEntry(
            index=i, bank=0, row=i, semantic_id=entry[2],
            symbol=entry[1], source="PRIOR_ACCEPTED_NATIVE_REGISTRY",
            active=True, teaching_candidate=True, reason="PRIOR_ACCEPTED_ABI",
        ) for i, entry in enumerate(abi_rows))
        snapshot = replace(
            _snapshot(),
            counts=AtlasCounts(
                1, 1, 1, len(entries), 1, len(entries), 0, 0, 0, 0),
            abi_entries=entries,
            semantic_lookup=tuple(sorted(
                (entry.semantic_id, entry.index) for entry in entries)),
        )
        span = SourceSpan(0, len(row["tokens"]))
        tree = bind_registered_source_row(
            adapter, row, snapshot, source_root=source_root, graph=graph,
            source_span=span, causal_prefix_end=span.end)
        query = row["record"]["query"]
        shape = inspect_source_query(query)
        schema, _ = _schema_for_symbol(
            snapshot, graph, shape.root, "source:" + query["kind"],
            adapter_id=adapter.descriptor.adapter_id, span=span,
            scope="source-query")
        self.assertEqual(tree.root.frame_schema_id, schema.schema_id)
        tag_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        manifest = seal_released_frame_schemas(
            (schema,), tag_map, snapshot)
        verified = load_released_frame_schemas(
            manifest.canonical_bytes(), expected_sha256=manifest.digest,
            snapshot=snapshot)
        self.assertEqual(
            verified.require_schema(
                schema, verified.lookup(schema.schema_id, schema.revision)),
            schema)

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

    def test_persisted_release_is_append_only_and_snapshot_bound(self):
        schema, tag_map, payload, digest, _ = _release()
        manifest = seal_released_frame_schemas(
            (schema,), tag_map, _snapshot())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = persist_released_frame_schemas(root, manifest)
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(persist_released_frame_schemas(root, manifest), path)
            with self.assertRaises(BilqisError) as caught:
                load_released_frame_schemas(
                    path.read_bytes(), expected_sha256=digest,
                    snapshot=replace(
                        _snapshot(), source_bundle_id="0" * 64))
            self.assertEqual(
                caught.exception.context["reason"],
                "FRAME_RELEASED_MANIFEST_ATLAS_SOURCE_MISMATCH")
            path.write_bytes(b"tampered")
            with self.assertRaises(BilqisError) as caught:
                persist_released_frame_schemas(root, manifest)
            self.assertEqual(
                caught.exception.context["reason"],
                "FRAME_RELEASED_MANIFEST_EXISTING_DRIFT")


if __name__ == "__main__":
    unittest.main()
