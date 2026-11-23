"""Numerical source compilation for ADR-153 ordinary BAMF training."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

from bilqis_mlx.generated_assessment import digest
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ApprovedFrame, EligibleContext, PUBLIC_FORMAL,
    SourceFrontier, _digest, _envelope_projection,
)
from bilqis_mlx.semantics.frame_adapters.public_formal_grants import _envelope
from bilqis_mlx.semantics.frame_adapters.registry import (
    _bind_verified_source_row, source_frame_strategy,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagEntry, SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import (
    FrameCompilerConfig, SourceAtom, StreamingAST,
)
from bilqis_mlx.semantics.frame_schema import SourceSpan, frame_schema_from_bytes
from bilqis_mlx.runtime.factory_training_context import public_training_context
from bilqis_mlx.runtime.factory_training_source_rows import _FactorySourceRow
from bilqis_mlx.runtime.atlas_training_contracts import _invalid


_SEMANTICS_ROOT = Path(__file__).resolve().parents[3] / "semantics"


def _walk(tree):
    yield tree.root
    for child in tree.children:
        yield from _walk(child)


@lru_cache(maxsize=16)
def _schema_bundle(source_family, release_sha256, bundle_id, source_bundle_id):
    """Read accepted schema data without re-authenticating pins on every step."""
    registry = json.loads(
        (_SEMANTICS_ROOT / "frame_schema_source_pins_v1.json").read_text())
    matches = tuple(
        item for item in registry["entries"]
        if item["family"] == source_family
        and item["semantic_release"] == release_sha256
        and item["atlas_bundle_id"] == bundle_id
        and item["source_bundle_id"] == source_bundle_id)
    if len(matches) != 1:
        _invalid("LEARNING_FIRST_SCHEMA_RELEASE_UNAVAILABLE")
    manifest = json.loads((
        _SEMANTICS_ROOT / "frame_schema_releases" /
        ("frame-schemas-" + matches[0]["schema_manifest_sha256"] + ".json")
    ).read_text())
    tag_map = manifest["schema_map"]
    schema_map = SchemaTagMap(
        semantic_release=tag_map["semantic_release"],
        entries=tuple(SchemaTagEntry(**entry) for entry in tag_map["entries"]),
        schema_version=tag_map["schema_version"],
    )
    schemas = tuple(
        frame_schema_from_bytes(body["canonical_body_json"].encode("utf-8"))
        for body in manifest["bodies"])
    return schemas, schema_map


def _learning_projection(tree, row, adapter_id, task, frontier, policy):
    visible_digest = digest({
        "source_id": row.get("source_id") or row.get("id"),
        "record": row.get("record"), "tokens": row.get("tokens")})
    envelopes = tuple(
        _envelope(
            frame,
            "learning-first:" + adapter_id + ":" + visible_digest + ":"
            + frame.occurrence_id,
            task, frontier, policy)
        for frame in _walk(tree))
    approved = tuple(sorted((
        ApprovedFrame(
            frame_handle=item.frame_handle,
            source_handle=item.source_handle,
            member_handles=tuple(member.source_handle for member in item.members),
            occurrence_id=item.frame.occurrence_id,
            content_digest=item.frame.content_digest,
            join_class=item.join_class,
            envelope_digest=_digest(_envelope_projection(item)),
        )
        for item in envelopes
    ), key=lambda item: item.frame_handle))
    eligible = EligibleContext(
        approved, (PUBLIC_FORMAL,),
        _digest({
            "schema": "bilqis.mlx.learning-first-context/v1",
            "frames": [item.envelope_digest for item in approved],
        }))
    return ApprovedContextProjection(
        eligible, tuple(sorted(envelopes, key=lambda item: item.frame_handle)))


def prepare_learning_first_source_row(
        source_context, authenticated, row, *, capability, source_seed, source_each):
    """Compile one already-selected lesson row without source/evidence replay."""
    if row.get("capability") != capability:
        from .atlas_training_contracts import _invalid
        _invalid("FACTORY_TRAINING_CAPABILITY_MISMATCH")
    adapter = source_context.source_registry.resolve_owner(row.get("generator"))
    strategy = source_frame_strategy(adapter.descriptor.adapter_id)
    _root, source_graph = strategy.graph_resolver(row)
    task, frontier, policy = public_training_context(
        authenticated.features.semantic_release, capability, len(row["tokens"]))
    span = SourceSpan(0, len(row["tokens"]))
    tree = _bind_verified_source_row(
        adapter, row, authenticated.snapshot, graph=source_graph,
        source_span=span, causal_prefix_end=span.end)
    projection = _learning_projection(
        tree, row, adapter.descriptor.adapter_id, task, frontier, policy)
    if strategy.source_family is None:
        schemas, schema_map = (), SchemaTagMap(task.semantic_release, ())
    else:
        schemas, schema_map = _schema_bundle(
            strategy.source_family, authenticated.snapshot.release_sha256,
            authenticated.snapshot.bundle_id, authenticated.snapshot.source_bundle_id)
    config = FrameCompilerConfig(
        schemas, schema_map, projection, task, frontier, policy)
    source_instance_id = tree.root.source_instance_id
    atoms = tuple(
        SourceAtom(
            position, source_graph["tokens"][token_index],
            "learning-first:" + adapter.descriptor.adapter_id + ":"
            + source_instance_id + ":" + str(position))
        for position, token_index in enumerate(row["tokens"]))
    ast = StreamingAST(source_instance_id, atoms, (tree,))
    profile = dict(
        source_context.release.execution_plan.capability_map[capability].provider_parameters)
    return _FactorySourceRow(
        row, adapter, None, profile or None, source_seed, source_each,
        source_instance_id, (tree,), ast, projection, source_graph, config,
        task, frontier, policy, (source_instance_id, (tree,)), projection,
        frontier, None)


def prepare_learning_first_source_rows(
        source_context, authenticated, rows, *, source_seed, source_each):
    return tuple(
        prepare_learning_first_source_row(
            source_context, authenticated, row, capability=row["capability"],
            source_seed=source_seed, source_each=source_each)
        for row in rows)


__all__ = ("prepare_learning_first_source_rows",)
