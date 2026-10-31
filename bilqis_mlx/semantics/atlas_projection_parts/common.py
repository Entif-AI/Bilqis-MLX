"""Atlas projection common ownership; canonical algorithms preserved."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from lib.ithkuil.src.skos.publication import json_bytes
from typing import NoReturn
import hashlib
import json
import re


ATLAS_RELEASE_SCHEMA = "bilqis.semantic-atlas-release/v1"

ATLAS_VALIDATION_SCHEMA = "bilqis.semantic-atlas-validation/v1"

ATLAS_ARTIFACT_SCHEMA = "bilqis.semantic-atlas-artifact/v1"

ATLAS_MANIFEST_SCHEMA = "bilqis.semantic-atlas-manifest/v1"

ATLAS_CONCEPT_RECORD_SCHEMA = "bilqis.semantic-atlas-concept/v1"

ATLAS_RELATION_RECORD_SCHEMA = "bilqis.semantic-atlas-relation/v1"

ATLAS_WITHHELD_RECORD_SCHEMA = "bilqis.semantic-atlas-withheld/v1"

ATLAS_SNAPSHOT_SCHEMA = "bilqis.semantic-atlas-snapshot/v1"

CONFORMANCE_SCHEMA = "bilqis.skos.conformance/v1"

COVERAGE_SCHEMA = "bilqis.skos.semantic-coverage/v1"

BANK_SIZE = 8192

NATIVE_REGISTRY_MIN_ROWS = 2

NATIVE_REGISTRY_HEADER_COLUMNS = 3

NATIVE_REGISTRY_SYMBOL_COLUMN = 1

NATIVE_REGISTRY_IDENTITY_COLUMN = 2

SHAPE_POLICY = {
    "schema": "bilqis.semantic-abi-shape-policy/v1",
    "bank_size": BANK_SIZE,
    "index_formula": "8192*bank+row",
    "extended_index_bits": 32,
    "fast_codec_max_exclusive": BANK_SIZE,
    "allocation_order": "prior-accepted-then-canonical-new-id",
    "new_row_state": "MASKED_UNTIL_ADMISSION",
}

REQUIRED_GATES = frozenset({"coverage", "no-omission", "determinism", "shacl"})

GATE_VERSIONS = {name: "1.0.0" for name in REQUIRED_GATES}

REQUIRED_BUNDLE_FILES = frozenset({
    "canonical.nt",
    "comparison.nt",
    "coverage.json",
    "source-rows.json",
    "conformance.json",
    "admitted-mappings.nt",
    "gate-coverage.json",
    "gate-no-omission.json",
    "gate-determinism.json",
    "gate-shacl.json",
})

HEX64 = re.compile(r"[0-9a-f]{64}\Z")

def _canonical_bytes(value: object) -> bytes:
    return json_bytes(value)

def _canonical_line(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

def _fail(reason: str) -> NoReturn:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)
