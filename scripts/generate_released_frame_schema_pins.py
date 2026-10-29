"""Stage A03 schema-body releases from actual pinned A01 and registered A/B/C.

This is a source-owner generator, not a neural admission action. The produced
pin registry must be independently reviewed and its digest pinned in code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bilqis_mlx.boolean_composite import (
    GENERATOR as COMPOSITE_GENERATOR, ORACLE as COMPOSITE_ORACLE,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_b_oracle import CONNECTIVES
from bilqis_mlx.live_grade_c import PLANS, registry_graph
from bilqis_mlx.numeric_curriculum import draw_numeric
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from bilqis_mlx.semantics.foundation.core import Apply
from bilqis_mlx.semantics.frame_adapters import (
    _APPEND_ONLY_NUMERIC_NODES, _schema_for_symbol,
    bind_registered_source_row,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap, _canonical_bytes
from bilqis_mlx.semantics.frame_schema import SourceSpan, ast_construct_id
from bilqis_mlx.semantics.released_frame_schemas import (
    persist_released_frame_schemas, seal_released_frame_schemas,
)
from bilqis_mlx.source_adapters.numeric import decode as decode_numeric
from bilqis_mlx.source_adapters.school import (
    A_ORACLE, B_ORACLE, C_ORACLE, live_source_registry,
)
from bilqis_mlx.source_adapters.structure import inspect_source_query


PIN_SCHEMA = "bilqis.frame-schema-source-pins/v1"
PIN_STATUS = "A03_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED"
ROOT = Path(__file__).resolve().parents[1]
SEMANTICS = ROOT / "bilqis_mlx/semantics"
SOURCE_ROOT = ROOT / "vendor/legacy-v16"


def _snapshot(artifact: Path):
    pin_file = SEMANTICS / "atlas_source_pins_v1.json"
    pins = json.loads(pin_file.read_bytes())["entries"]
    matches = [pin for pin in pins if pin["bundle_id"] == artifact.name]
    if len(matches) != 1:
        raise ValueError("A01 source artifact is not in the repo-owned pin registry")
    pin = matches[0]
    return load_pinned_atlas_snapshot(AtlasArtifactSelection(
        str(artifact), pin["bundle_id"], pin["release_sha256"],
        pin["source_bundle_id"]))


def _add(catalog: dict, schema) -> None:
    key = schema.schema_id, schema.revision
    previous = catalog.get(key)
    if previous is not None and previous.canonical_bytes() != schema.canonical_bytes():
        raise ValueError(f"same-ID A03 schema-body conflict: {key}")
    catalog[key] = schema


def _source_schemas(node, *, adapter, graph, snapshot, span, catalog):
    shape = inspect_source_query(node)
    schema, _ = _schema_for_symbol(
        snapshot, graph, shape.root, "source:" + node["kind"],
        adapter_id=adapter.descriptor.adapter_id, span=span,
        scope="source-query")
    _add(catalog, schema)
    for child in node.get("args", ()):
        if isinstance(child, dict) and child.get("kind") in {
                "compare", "relation", "apply", "op"}:
            _source_schemas(
                child, adapter=adapter, graph=graph, snapshot=snapshot,
                span=span, catalog=catalog)


def _numeric_schemas(node, *, adapter, graph, snapshot, span, catalog):
    if not isinstance(node, Apply):
        return
    schema, _ = _schema_for_symbol(
        snapshot, graph, node.operator.symbol, ast_construct_id(node),
        adapter_id=adapter.descriptor.adapter_id, span=span,
        scope="formal-expression",
        contract_sha256=(
            node.operator.contract_sha256
            if node.operator.symbol in _APPEND_ONLY_NUMERIC_NODES else None))
    _add(catalog, schema)
    for child in node.arguments:
        _numeric_schemas(
            child, adapter=adapter, graph=graph, snapshot=snapshot,
            span=span, catalog=catalog)


def _checked_row(adapter, row, snapshot, graph):
    span = SourceSpan(0, len(row["tokens"]))
    bind_registered_source_row(
        adapter, row, snapshot, source_root=SOURCE_ROOT,
        graph=graph, source_span=span, causal_prefix_end=span.end)
    return span


def _catalogs(snapshot):
    micro = read_sources(SOURCE_ROOT)[2]
    numeric = registry_graph()
    registry = live_source_registry()
    catalogs = {family: {} for family in ("micro", "boolean", "numeric")}

    adapter = registry.require(
        "bilqis_mlx.grade_a_probe.make_record", A_ORACLE)
    for capability in (
            "A.IDENTITY", "A.PARENT", "A.LINK",
            "A.MEMBER", "A.EDGE", "A.MAPS"):
        row = adapter.draw(
            source_root=SOURCE_ROOT, graph=micro, course=None,
            capability=capability, seed=31, each=2)[0]
        span = _checked_row(adapter, row, snapshot, micro)
        _source_schemas(
            row["record"]["query"], adapter=adapter, graph=micro,
            snapshot=snapshot, span=span, catalog=catalogs["micro"])

    adapter = registry.require(
        "bilqis_mlx.live_grade_b.draw_connectives", B_ORACLE)
    for name in CONNECTIVES:
        row = adapter.draw(
            source_root=SOURCE_ROOT, graph=micro, course=None,
            capability="B." + name, seed=31, each=4)[0]
        span = _checked_row(adapter, row, snapshot, micro)
        _source_schemas(
            row["record"]["query"], adapter=adapter, graph=micro,
            snapshot=snapshot, span=span, catalog=catalogs["boolean"])
    adapter = registry.require(COMPOSITE_GENERATOR, COMPOSITE_ORACLE)
    row = adapter.draw(
        source_root=SOURCE_ROOT, graph=micro, course=None,
        capability="B.COMPOSITE", seed=37, each=4)[0]
    span = _checked_row(adapter, row, snapshot, micro)
    _source_schemas(
        row["record"]["query"], adapter=adapter, graph=micro,
        snapshot=snapshot, span=span, catalog=catalogs["boolean"])

    adapter = registry.require(
        "bilqis_mlx.numeric_curriculum.draw_numeric", C_ORACLE)
    for capability in (
            "C.COUNT", "C.NUMBER", "C.SUCCESSOR",
            "C.ADD", "C.SUB", "C.MUL", "C.DIV"):
        row = draw_numeric(
            PLANS, numeric, seed=29, maximum=3, each=3,
            capability=capability)[0]
        span = _checked_row(adapter, row, snapshot, numeric)
        _numeric_schemas(
            decode_numeric(row["record"]["symbols"]),
            adapter=adapter, graph=numeric, snapshot=snapshot,
            span=span, catalog=catalogs["numeric"])
    return catalogs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas-artifact", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=(
        SEMANTICS / "frame_schema_releases"))
    parser.add_argument("--pin-registry", type=Path, default=(
        SEMANTICS / "frame_schema_source_pins_v1.json"))
    args = parser.parse_args()
    snapshot = _snapshot(args.atlas_artifact.resolve())
    catalogs = _catalogs(snapshot)
    pins = []
    for family, catalog in sorted(catalogs.items()):
        schemas = tuple(catalog.values())
        tag_map = SchemaTagMap.from_schemas(
            snapshot.release_sha256, schemas)
        manifest = seal_released_frame_schemas(
            schemas, tag_map, snapshot)
        path = persist_released_frame_schemas(args.output_dir, manifest)
        pins.append({
            "family": family,
            "semantic_release": snapshot.release_sha256,
            "atlas_bundle_id": snapshot.bundle_id,
            "source_bundle_id": snapshot.source_bundle_id,
            "schema_manifest_sha256": manifest.digest,
            "schema_map_sha256": tag_map.digest,
            "source_receipt": "docs/evidence/bamf/A03.4/receipt.md",
            "status": PIN_STATUS,
        })
        print(f"{family}: {len(schemas)} bodies; {path.name}; map={tag_map.digest}")
    payload = _canonical_bytes({"schema": PIN_SCHEMA, "entries": pins})
    if args.pin_registry.exists() and args.pin_registry.read_bytes() != payload:
        raise ValueError("existing A03 source pin registry drift: review before replacement")
    args.pin_registry.write_bytes(payload)
    print("A03_PIN_REGISTRY_SHA256", hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    main()
