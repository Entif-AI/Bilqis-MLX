"""Versioned source of truth for the *historical* model ABI.

Current admitted vocabulary may grow beyond this protected prefix. Only this
module reads the original code-owned ABI manifest; all callers import the
same named historical contract rather than copying a literal model size.
The digest includes index, token symbol, semantic ID, and source row contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping


ABI_MANIFEST = Path(__file__).with_name("legacy_abi_v1.json")
ABI_SCHEMA = "bilqis.semantic-abi/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class HistoricalABI:
    release: str
    prefix_tokens: int
    checkpoint_sha256: str
    graph_sha256: str
    index_contract_sha256: str
    source_fields_sha256: str

    @classmethod
    def from_manifest(cls, source: Path = ABI_MANIFEST) -> "HistoricalABI":
        raw = json.loads(Path(source).read_text(encoding="utf-8"))
        if raw.get("schema") != ABI_SCHEMA:
            raise ValueError("HISTORICAL_ABI_SCHEMA_INVALID")
        names = ("release", "historical_prefix_tokens", "historical_checkpoint_sha256",
                 "historical_graph_sha256", "historical_index_contract_sha256",
                 "historical_source_fields_sha256")
        if set(raw) != {"schema", *names}:
            raise ValueError("HISTORICAL_ABI_FIELDS_INVALID")
        if not isinstance(raw["release"], str) or not raw["release"].strip():
            raise ValueError("HISTORICAL_ABI_RELEASE_INVALID")
        if type(raw["historical_prefix_tokens"]) is not int or raw["historical_prefix_tokens"] < 1:
            raise ValueError("HISTORICAL_ABI_SIZE_INVALID")
        for field in names[2:]:
            if not isinstance(raw[field], str) or not _SHA256.fullmatch(raw[field]):
                raise ValueError("HISTORICAL_ABI_DIGEST_INVALID:" + field)
        return cls(raw["release"], raw["historical_prefix_tokens"],
                   raw["historical_checkpoint_sha256"], raw["historical_graph_sha256"],
                   raw["historical_index_contract_sha256"], raw["historical_source_fields_sha256"])


HISTORICAL_ABI = HistoricalABI.from_manifest()
HISTORICAL_PREFIX_SIZE = HISTORICAL_ABI.prefix_tokens


def _fingerprint(rows: list[dict[str, object]]) -> str:
    serialized = json.dumps(rows, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _original_sheet_rows(snapshot: Mapping, abi: HistoricalABI) -> list:
    try:
        rows = [row for row in snapshot["tabs"]["Token Atlas"]["rows"][1:]
                if int(row[0]) < abi.prefix_tokens]
        rows.sort(key=lambda row: int(row[0]))
        if ([int(row[0]) for row in rows] != list(range(abi.prefix_tokens)) or
                any(row[14] != abi.graph_sha256 for row in rows)):
            raise ValueError("HISTORICAL_ABI_SNAPSHOT_INDEX_DRIFT")
        return rows
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ValueError("HISTORICAL_ABI_SNAPSHOT_INVALID") from exc


def fingerprint_sheet_source_fields(snapshot: Mapping, *,
                                    abi: HistoricalABI = HISTORICAL_ABI) -> str:
    """Bind ALL legacy source-observable meaning, signature and type fields.

    A spreadsheet's asserted row-contract digest alone cannot prove its
    human-readable semantic fields stayed intact. This is pinned separately.
    """
    rows = _original_sheet_rows(snapshot, abi)
    return _fingerprint([{
        "index": int(row[0]), "symbol": row[1], "identity": row[2],
        "meaning": row[3], "signature": row[4], "family": row[5],
        "subtype": row[6], "arity": row[11], "stage": row[12],
        "contract_sha256": row[13], "graph_sha256": row[14],
    } for row in rows])


def fingerprint_sheet_prefix(snapshot: Mapping, *, abi: HistoricalABI = HISTORICAL_ABI) -> str:
    """Derive the original-index contract from actual indexed registry rows.

    Sheet display order is irrelevant; machine index/identity/contract are not.
    Additional newly admitted rows cannot replace or renumber the old prefix.
    """
    rows = _original_sheet_rows(snapshot, abi)
    if fingerprint_sheet_source_fields(snapshot, abi=abi) != abi.source_fields_sha256:
        raise ValueError("HISTORICAL_ABI_SOURCE_FIELDS_MISMATCH")
    identifiers = [{"index": int(row[0]), "symbol": row[1],
                    "identity": row[2], "contract_sha256": row[13]}
                   for row in rows]
    return _fingerprint(identifiers)


def fingerprint_graph_prefix(graph: Mapping, *, abi: HistoricalABI = HISTORICAL_ABI) -> str:
    """Check entire saved graph prefix including source semantic row digests."""
    try:
        nodes = graph["nodes"]
        receipts = graph["row_contract_sha256"]
        if len(nodes) < abi.prefix_tokens:
            raise ValueError("HISTORICAL_ABI_MODEL_TOO_SMALL")
        if any(graph["tokens"][index] != node["id"] or
               receipts[node["id"]] != _fingerprint_node(node)
               for index, node in enumerate(nodes[:abi.prefix_tokens])):
            raise ValueError("HISTORICAL_ABI_SOURCE_NODE_DRIFT")
        rows = [{"index": index, "symbol": node["id"],
                 "identity": node.get("semantic_id") or "legacy:" + node["id"],
                 "contract_sha256": receipts[node["id"]]}
                for index, node in enumerate(nodes[:abi.prefix_tokens])]
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("HISTORICAL_ABI_GRAPH_INVALID") from exc
    return _fingerprint(rows)


def _fingerprint_node(node: dict) -> str:
    return hashlib.sha256(json.dumps(node, sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")).hexdigest()


def require_historical_prefix(actual_fingerprint: str, *, abi: HistoricalABI = HISTORICAL_ABI) -> None:
    if actual_fingerprint != abi.index_contract_sha256:
        raise ValueError("HISTORICAL_ABI_PREFIX_MISMATCH")


def prefix_preserving_vocab_size(graph: Mapping, *, allow_growth: bool = False,
                                 abi: HistoricalABI = HISTORICAL_ABI) -> int:
    """Observe a graph's vocabulary size; never imply a growth admission.

    Growth approval is a separate release/teacher/trainer contract. This only
    establishes that an observed graph has not reinterpreted old token slots.
    """
    require_historical_prefix(fingerprint_graph_prefix(graph, abi=abi), abi=abi)
    actual = len(graph["tokens"])
    if actual != len(graph["nodes"]):
        raise ValueError("HISTORICAL_ABI_MODEL_GRAPH_COUNT_DRIFT")
    if (not allow_growth and actual != abi.prefix_tokens):
        raise ValueError("HISTORICAL_ABI_NOT_ORIGINAL_RELEASE")
    return actual


def require_external_expected(expected_sha256: str | None,
                              *, required: bool = False,
                              abi: HistoricalABI = HISTORICAL_ABI) -> bool:
    """Fail closed for enforced CI; report missing external trust separately."""
    if not expected_sha256:
        if required:
            raise ValueError("HISTORICAL_ABI_EXTERNAL_REFERENCE_MISSING")
        return False
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError("HISTORICAL_ABI_EXTERNAL_REFERENCE_INVALID")
    if expected_sha256 != abi.source_fields_sha256:
        raise ValueError("HISTORICAL_ABI_EXTERNAL_REFERENCE_MISMATCH")
    return True
