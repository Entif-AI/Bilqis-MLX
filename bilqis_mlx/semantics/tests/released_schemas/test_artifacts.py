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


class ReleasedArtifactsTests(unittest.TestCase):
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

