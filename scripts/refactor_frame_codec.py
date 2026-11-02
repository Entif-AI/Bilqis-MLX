#!/usr/bin/env python3
"""Split the oversized frame codec and its tests into cohesive modules."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess
import textwrap


ROOT = Path(__file__).resolve().parents[1]
CODEC = Path("bilqis_mlx/semantics/frame_codec.py")
TEST = Path("bilqis_mlx/semantics/tests/test_frame_codec.py")

ROLE_INDEX_SPLIT = '''def test_role_index_is_codec_neutral_for_compact_and_extended(self):
    schema = _schema("A")
    schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
    active_snapshot = _snapshot()
    compact = _frame(
        schema, tuple(_concept(index) for index in range(4)),
        source_instance_id="compact-active",
    )
    packed_compact = pack_frame(
        compact, schema=schema, schema_map=schema_map)
    self.assertEqual(
        role_index(
            packed_compact,
            "slot2",
            0,
            schema_map=schema_map,
            snapshot=active_snapshot,
        ),
        2,
    )

    five_schema = FrameSchema(
        "frame:FIVE",
        1,
        "source:FIVE",
        tuple(RoleSpec("slot" + str(i), ("Entity",), 1, 1)
              for i in range(5)),
        "ORDERED",
        "fixture",
    )
    five_map = SchemaTagMap.from_schemas(RELEASE, (five_schema,))
    five = _frame(
        five_schema, tuple(_concept(index) for index in range(5)),
        source_instance_id="extended-active",
    )
    packed_extended = pack_frame(
        five, schema=five_schema, schema_map=five_map)
    self.assertEqual(
        role_index(
            packed_extended,
            "slot4",
            0,
            schema_map=five_map,
            snapshot=active_snapshot,
        ),
        4,
    )

def test_role_index_rejects_inactive_readout(self):
    schema = _schema("A")
    schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
    inactive = _frame(
        schema,
        (_concept(0), _concept(1), _concept(2), _concept(4)),
        source_instance_id="compact-inactive",
    )
    packed_inactive = pack_frame(
        inactive, schema=schema, schema_map=schema_map)
    self.assertEqual(packed_inactive.disposition, PackDisposition.COMPACT)
    with self.assertRaises(BilqisError) as caught:
        role_index(
            packed_inactive,
            "slot3",
            0,
            schema_map=schema_map,
            snapshot=_snapshot(inactive=(4,)),
        )
    self.assertEqual(caught.exception.context["reason"],
                     "FRAME_READOUT_INDEX_INACTIVE")

def test_role_index_rejects_held_readout(self):
    schema = _schema("A")
    schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
    held_id = "held:semantic"
    held = _frame(
        schema,
        (_concept(0), _concept(1), _concept(2),
         _concept(0, semantic_id=held_id)),
        source_instance_id="compact-held-alias",
    )
    packed_held = pack_frame(
        held, schema=schema, schema_map=schema_map)
    with self.assertRaises(BilqisError) as caught:
        role_index(
            packed_held,
            "slot3",
            0,
            schema_map=schema_map,
            snapshot=_snapshot(held_id=held_id),
        )
    self.assertEqual(caught.exception.context["reason"],
                     "FRAME_READOUT_SEMANTIC_HELD")'''


def _git_text(ref: str, path: Path) -> str:
    return subprocess.check_output(
        ["git", "show", f"{ref}:{path.as_posix()}"], cwd=ROOT, text=True
    )


def _nodes(source: str) -> dict[str, ast.AST]:
    tree = ast.parse(source)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }


def _segment(source: str, node: ast.AST) -> str:
    lines = source.splitlines()
    assert hasattr(node, "lineno") and hasattr(node, "end_lineno")
    decorators = getattr(node, "decorator_list", ())
    start = min((item.lineno for item in decorators), default=node.lineno)
    return "\n".join(lines[start - 1 : node.end_lineno]) + "\n"


def _definitions(source: str, names: tuple[str, ...]) -> str:
    nodes = _nodes(source)
    return "\n".join(_segment(source, nodes[name]).rstrip() for name in names) + "\n"


def _write(path: Path, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def _split_codec(source: str) -> None:
    prefix = "from __future__ import annotations\n\n"
    common = prefix + '''from enum import Enum\nimport hashlib\nimport json\nimport re\n\nfrom ...errors import ErrorBus, SEMANTIC_FRAME\n\nCOMPACT_CODEC_ID = "bamf.frame-u64/v1"\nSCHEMA_MAP_SCHEMA = "bilqis.frame-schema-tag-map/v1"\nSCHEMA_TAG_ENTRY_SCHEMA = "bilqis.frame-schema-tag-entry/v1"\nSLOT_TUPLE_SCHEMA = "bilqis.frame-slot-tuple/v1"\nCOMPACT_BYTES_SCHEMA = "bilqis.frame-u64-bytes/v1"\nPACKED_FRAME_SCHEMA = "bilqis.packed-frame/v1"\nEXTENDED_SLOT_SCHEMA = "bilqis.extended-frame-slot/v1"\nFRAME_SIDECAR_SCHEMA = "bilqis.frame-codec-sidecar/v1"\nCONSTITUENT_METADATA_SCHEMA = "bilqis.frame-constituent-metadata/v1"\nEXTENDED_CODEC_ID = "bamf.frame-extended/v1"\nATOMIC_CODEC_ID = "bamf.frame-atomic/v1"\n\nSLOT_COUNT = 4\nSLOT_BITS = 13\nSLOT_LIMIT = 1 << SLOT_BITS\nSLOT_MASK = SLOT_LIMIT - 1\nPRESENCE_SHIFT = SLOT_COUNT * SLOT_BITS\nPRESENCE_MASK = (1 << SLOT_COUNT) - 1\nSCHEMA_SHIFT = PRESENCE_SHIFT + SLOT_COUNT\nSCHEMA_BITS = 4\nSCHEMA_LIMIT = 1 << SCHEMA_BITS\nSCHEMA_MASK = SCHEMA_LIMIT - 1\nVERSION_SHIFT = SCHEMA_SHIFT + SCHEMA_BITS\nVERSION_BITS = 4\nVERSION_MASK = (1 << VERSION_BITS) - 1\nCODEC_VERSION = 1\nU64_BITS = 64\nU64_LIMIT = 1 << U64_BITS\nU64_BYTES = 8\nUINT32_BITS = 32\nUINT32_LIMIT = 1 << UINT32_BITS\n\n_SHA256 = re.compile(r"[0-9a-f]{64}\\Z")\n\n'''
    common += _definitions(
        source, ("_fail", "_canonical_bytes", "_digest", "PackDisposition", "FallbackReason")
    )
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/common.py"), common)

    schema_tags = prefix + '''from dataclasses import asdict, dataclass\nimport hashlib\n\nfrom .common import (\n    CODEC_VERSION, COMPACT_BYTES_SCHEMA, COMPACT_CODEC_ID, PRESENCE_MASK,\n    SCHEMA_LIMIT, SCHEMA_MAP_SCHEMA, SCHEMA_TAG_ENTRY_SCHEMA, SLOT_COUNT,\n    SLOT_LIMIT, SLOT_TUPLE_SCHEMA, U64_BYTES, _SHA256, _digest, _fail,\n)\n\n'''
    schema_tags += _definitions(
        source, ("SchemaTagEntry", "SchemaTagMap", "SlotTuple", "CompactFrameBytes")
    )
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/schema_tags.py"), schema_tags)

    metadata = prefix + '''from dataclasses import asdict, dataclass\n\nfrom ..frame_schema import BindingState, SourceSpan\nfrom .common import (\n    ATOMIC_CODEC_ID, COMPACT_CODEC_ID, CONSTITUENT_METADATA_SCHEMA,\n    EXTENDED_CODEC_ID, EXTENDED_SLOT_SCHEMA, FRAME_SIDECAR_SCHEMA, UINT32_LIMIT,\n    _SHA256, _digest, _fail,\n)\n\n'''
    metadata += _definitions(
        source, ("ExtendedSlot", "ConstituentMetadata", "FrameSidecar")
    )
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/metadata.py"), metadata)

    packed = prefix + '''from dataclasses import asdict, dataclass\n\nfrom .common import (\n    ATOMIC_CODEC_ID, COMPACT_CODEC_ID, EXTENDED_CODEC_ID, PACKED_FRAME_SCHEMA,\n    FallbackReason, PackDisposition, _SHA256, _digest, _fail,\n)\nfrom .metadata import ExtendedSlot, FrameSidecar\n\n'''
    packed += _definitions(source, ("PackDecision", "PackedFrame"))
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/packed.py"), packed)

    compact = prefix + '''from .common import (\n    CODEC_VERSION, COMPACT_CODEC_ID, PRESENCE_MASK, PRESENCE_SHIFT, SCHEMA_LIMIT,\n    SCHEMA_MASK, SCHEMA_SHIFT, SLOT_BITS, SLOT_COUNT, SLOT_LIMIT, SLOT_MASK,\n    U64_BYTES, U64_LIMIT, VERSION_MASK, VERSION_SHIFT, _fail,\n)\nfrom .schema_tags import CompactFrameBytes, SchemaTagMap, SlotTuple\n\n'''
    compact += _definitions(source, ("pack4", "unpack4", "serialize_u64", "deserialize_u64"))
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/compact.py"), compact)

    classification = prefix + '''from ..frame_schema import AtomicFrame, BindingState, FrameInstance, FrameSchema\nfrom .common import FallbackReason, PackDisposition, SLOT_COUNT, SLOT_LIMIT, _fail\nfrom .packed import PackDecision\nfrom .schema_tags import SchemaTagMap\n\n'''
    classification += _definitions(
        source, ("_frame_semantic_release", "_validate_frame_schema_shape", "classify_frame")
    )
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/classification.py"), classification)

    payload = prefix + '''from dataclasses import asdict\nimport hashlib\nimport json\n\nfrom ..frame_schema import (\n    AtomicFrame, FrameInstance, FrameSchema, RoleOccurrence, SourceSpan,\n)\nfrom .common import ATOMIC_CODEC_ID, _canonical_bytes, _fail\nfrom .metadata import ConstituentMetadata, ExtendedSlot, FrameSidecar\nfrom .schema_tags import SchemaTagMap\n\n'''
    payload += _definitions(
        source,
        ("_extended_slot", "_constituent_metadata", "_frame_sidecar", "_atomic_payload", "_atomic_from_payload"),
    )
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/payload.py"), payload)

    pack = prefix + '''import hashlib\n\nfrom ..frame_schema import AtomicFrame, FrameInstance, FrameSchema\nfrom .classification import classify_frame\nfrom .common import ATOMIC_CODEC_ID, COMPACT_CODEC_ID, EXTENDED_CODEC_ID, PackDisposition\nfrom .compact import pack4\nfrom .packed import PackedFrame\nfrom .payload import _atomic_payload, _extended_slot, _frame_sidecar\nfrom .schema_tags import SchemaTagMap\n\n'''
    pack += _definitions(source, ("pack_frame",))
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/pack.py"), pack)

    unpack = prefix + '''import hashlib\nimport json\n\nfrom ..atlas_projection import FrozenAtlasSnapshot\nfrom ..frame_schema import (\n    AtomicFrame, BindingState, FrameInstance, FrameSchema, RoleSpec,\n    frame_instance_from_bytes,\n)\nfrom .classification import _validate_frame_schema_shape\nfrom .common import PackDisposition, _fail\nfrom .compact import unpack4\nfrom .metadata import ExtendedSlot\nfrom .packed import PackedFrame\nfrom .payload import _atomic_from_payload, _extended_slot, _frame_sidecar\nfrom .schema_tags import SchemaTagMap\n\n'''
    unpack += _definitions(
        source,
        ("_validate_schema_sidecar", "_validate_extended_slots", "_validate_frame_sidecar", "unpack_frame", "role_index"),
    )
    _write(Path("bilqis_mlx/semantics/frame_codec_parts/unpack.py"), unpack)

    _write(Path("bilqis_mlx/semantics/frame_codec_parts/__init__.py"), "")
    facade = prefix + '''"""Reversible compact and extended encodings for released semantic frames."""\n\nfrom .frame_codec_parts.common import (\n    ATOMIC_CODEC_ID, CODEC_VERSION, COMPACT_CODEC_ID, EXTENDED_CODEC_ID,\n    PRESENCE_MASK, PRESENCE_SHIFT, SCHEMA_SHIFT, VERSION_SHIFT,\n    FallbackReason, PackDisposition, _canonical_bytes,\n)\nfrom .frame_codec_parts.schema_tags import (\n    CompactFrameBytes, SchemaTagEntry, SchemaTagMap, SlotTuple,\n)\nfrom .frame_codec_parts.metadata import (\n    ConstituentMetadata, ExtendedSlot, FrameSidecar,\n)\nfrom .frame_codec_parts.packed import PackDecision, PackedFrame\nfrom .frame_codec_parts.compact import pack4, unpack4, serialize_u64, deserialize_u64\nfrom .frame_codec_parts.classification import classify_frame\nfrom .frame_codec_parts.pack import pack_frame\nfrom .frame_codec_parts.unpack import role_index, unpack_frame\n\n__all__ = (\n    "ATOMIC_CODEC_ID", "CODEC_VERSION", "COMPACT_CODEC_ID", "EXTENDED_CODEC_ID",\n    "PRESENCE_MASK", "PRESENCE_SHIFT", "SCHEMA_SHIFT", "VERSION_SHIFT",\n    "FallbackReason", "PackDisposition", "CompactFrameBytes", "SchemaTagEntry",\n    "SchemaTagMap", "SlotTuple", "ConstituentMetadata", "ExtendedSlot",\n    "FrameSidecar", "PackDecision", "PackedFrame", "pack4", "unpack4",\n    "serialize_u64", "deserialize_u64", "classify_frame", "pack_frame",\n    "role_index", "unpack_frame", "_canonical_bytes",\n)\n'''
    _write(CODEC, facade)


def _class_methods(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    lines = source.splitlines()
    return {
        node.name: "\n".join(lines[node.lineno - 1 : node.end_lineno])
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
    }


def _split_tests(source: str) -> None:
    lines = source.splitlines()
    cls = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))
    helper = "\n".join(lines[: cls.lineno - 1]).rstrip() + "\n\n"
    helper += "__all__ = tuple(name for name in globals() if not name.startswith('__'))\n"
    base = Path("bilqis_mlx/semantics/tests/frame_codec_cases")
    _write(base / "helpers.py", helper)
    _write(base / "__init__.py", "")
    methods = _class_methods(source)
    groups = {
        "contracts.py": (
            "ContractMixin",
            (
                "test_singular_schema_role_cannot_fall_back_to_extended_when_duplicated",
                "test_packed_frame_must_match_authoritative_schema_role_order",
                "test_role_type_mismatch_is_not_a_codec_fallback",
                "test_literal_bit_layout_and_roundtrip",
                "test_all_zero_indices_and_all_max_fields_match_literal_words",
                "test_zero_index_is_present_not_empty",
                "test_range_version_presence_and_unknown_tag_fail_closed",
                "test_schema_map_is_release_local_content_addressed_and_schema_exact",
                "test_little_endian_eight_bytes_and_decimal_json_are_literal",
            ),
        ),
        "fallback.py": (
            "FallbackMixin",
            (
                "test_pack_frame_compact_and_extended_reconstruct_exactly",
                "test_index8192_five_slots_and_nested_child_choose_extended",
                "test_partial_and_atomic_fallback_are_typed_not_exception_driven",
            ),
        ),
        "readout.py": (
            "ReadoutMixin",
            (
                "test_wrong_release_or_schema_map_refuses_sidecar_reinterpretation",
                "test_payload_and_sidecar_cannot_rebind_another_schema_or_release",
            ),
        ),
        "boundaries.py": (
            "BoundaryMixin",
            (
                "test_extended_uint32_upper_boundary_roundtrips_and_overflow_rejects",
                "test_constituent_sidecar_preserves_order_source_and_occurrence",
            ),
        ),
    }
    for filename, (class_name, names) in groups.items():
        parts = [methods[name] for name in names]
        if filename == "readout.py":
            parts.insert(0, ROLE_INDEX_SPLIT)
        body = "\n\n".join(parts)
        content = (
            "from __future__ import annotations\n\n"
            "from bilqis_mlx.semantics.tests.frame_codec_cases.helpers import *  # noqa: F403\n\n\n"
            f"class {class_name}:\n"
            + textwrap.indent(textwrap.dedent(body), "    ")
            + "\n"
        )
        _write(base / filename, content)

    wrapper = '''from __future__ import annotations\n\nimport unittest\n\nfrom bilqis_mlx.semantics.frame_codec import SchemaTagMap\nfrom bilqis_mlx.semantics.tests.frame_codec_cases.boundaries import BoundaryMixin\nfrom bilqis_mlx.semantics.tests.frame_codec_cases.contracts import ContractMixin\nfrom bilqis_mlx.semantics.tests.frame_codec_cases.fallback import FallbackMixin\nfrom bilqis_mlx.semantics.tests.frame_codec_cases.helpers import RELEASE, _schema\nfrom bilqis_mlx.semantics.tests.frame_codec_cases.readout import ReadoutMixin\n\n\nclass CompactFrameCodecTests(\n    ContractMixin, FallbackMixin, ReadoutMixin, BoundaryMixin, unittest.TestCase\n):\n    def setUp(self):\n        self.schemas = tuple(_schema(name) for name in ("A", "B", "C", "D"))\n        self.schema_map = SchemaTagMap.from_schemas(RELEASE, self.schemas)\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''
    _write(TEST, wrapper)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-ref", required=True)
    args = parser.parse_args()
    _split_codec(_git_text(args.source_ref, CODEC))
    _split_tests(_git_text(args.source_ref, TEST))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
