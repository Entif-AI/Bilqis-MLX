"""Released-schema io witnesses."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.semantics.atlas_projection import AbiEntry
from bilqis_mlx.semantics.atlas_projection import AtlasCounts
from bilqis_mlx.semantics.frame_adapters import (
    _schema_for_symbol, bind_registered_source_row,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import (
    load_released_frame_schemas, persist_released_frame_schemas,
    seal_released_frame_schemas,
)
from bilqis_mlx.source_adapters.school import A_ORACLE, live_source_registry
from bilqis_mlx.source_adapters.structure import inspect_source_query
from bilqis_mlx.semantics.tests.released_schemas.fixtures import (
    RELEASE, _snapshot, _schema, _release,
)


class ReleasedIoTests(unittest.TestCase):
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
