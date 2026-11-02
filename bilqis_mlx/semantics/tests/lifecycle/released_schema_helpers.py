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



