"""Conserved one-to-one Bilqis token / pasigraphy registry projection.

This is an evidence projection, not a lexical root generator. Legacy graph
node meanings remain source-defined and subject to NI conformance review.
New models cannot silently introduce tokens absent from this mapping, and an
unregistered research seed never becomes part of the model vocabulary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .backup import digest_file
from .source import AUDITED_PARENT
from .vocabulary_growth import _check_catalog, digest

SCHEMA = "bilqis.mlx.pasigraphy-token-atlas/v1"
REGISTRY_SHEET = "Token Atlas"
ORIGINAL_GRAPH_DIGEST = "57ab0a141a9bfc25c6da8d0568f14e0a8beaab2c0c3fd33931e51e2624a0b16f"
COLUMNS = (
    "0-based Token ID", "Bilqis token symbol", "Pasigraphy identity",
    "Source-grounded semantic role/function", "Formal signature", "Semantic family",
    "Source subtype", "Arity", "Source stage", "Node contract SHA-256",
    "Source graph SHA-256", "NI bridge or grammar locus", "Lesson provenance",
    "Token mastery evidence", "Meaning-review status", "Historical source / notes",
)


def identity(node: dict) -> str:
    """Every source token has one stable catalog ID, distinct from its literal name."""
    return node.get("semantic_id") or "legacy:" + node["id"]


def role(node: dict) -> str:
    """Read meaning from the source node, never infer an unattested NI mapping."""
    if "meaning" in node:
        return node["meaning"]
    token = node["id"]
    family = node["family"]
    subtype = node["subtype"]
    signature = node["signature"]
    # A source node is a typed semantic function even when it is not a lexical root.
    if family == "integer" and token.startswith("school.number."):
        return "Typed numeral for exact integer " + token.rsplit(".", 1)[-1]
    if family == "Boolean" and subtype == "operator":
        values = node.get("truth_signature", [])
        return f"Boolean operation {token.rsplit('.',1)[-1]} with source truth signature {values}"
    if family == "syntax":
        return f"Syntactic or task-control function {token} (source type {signature}); exact surface role needs independent review"
    if family == "Boolean" and subtype == "literal":
        return "Boolean literal " + token.rsplit(".",1)[-1]
    if family == "Boolean" and subtype == "free_variable":
        return "Typed Boolean variable " + token.rsplit(".",1)[-1]
    return f"Source-defined {family} / {subtype} relation or value ({signature}), represented by {token}"


def validate_one_to_one(graph: dict) -> None:
    _check_catalog(graph)
    identifiers = [identity(n) for n in graph["nodes"]]
    if any(not isinstance(key,str) or not key.strip() for key in identifiers):
        raise ValueError("PASIGRAPHY_TOKEN_HAS_NO_IDENTITY")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("PASIGRAPHY_DUPLICATE_SEMANTIC_IDENTITY")
    for node in graph["nodes"]:
        if (not node.get("family") or not node.get("subtype") or
                not node.get("signature") or not role(node).strip()):
            raise ValueError("PASIGRAPHY_UNINTERPRETABLE_TOKEN:"+node["id"])
        if node.get("semantic_id") is not None and (
                not node.get("meaning") or not node.get("source") or
                not node.get("admission_receipt")):
            raise ValueError("PASIGRAPHY_NEW_IDENTITY_NOT_DEFINED:"+node["id"])


def rows_for_graph(graph: dict) -> list[list[str]]:
    validate_one_to_one(graph)
    graph_sha = digest(graph)
    result=[]
    for token_index, node in enumerate(graph["nodes"]):
        new = "semantic_id" in node
        record = [
            str(token_index), node["id"], identity(node), role(node),
            node["signature"],node["family"],node["subtype"],
            str(node["arity"]),str(node["stage"]),
            graph["row_contract_sha256"][node["id"]],graph_sha,
            "UNMAPPED_TO_NI_NOT_ASSERTED",
            "ADMITTED_NOT_YET_TAUGHT" if new else "HISTORICAL_SOURCE_DEFINED",
            "NO_SAME_CHECKPOINT_TOKEN_MASTERY_PROOF",
            "NI_CONFORMANCE_UNVERIFIED" if new else "LEGACY_MEANING_NEEDS_HUMAN_REVIEW",
            ("new:"+node["source"]) if new else "historical_complete_student:source_graph",
        ]
        result.append(record)
    return result


def verify_sheet_rows(graph: dict, rows: list[list[object]], *, require_header: bool=True) -> dict:
    """Fail when *any* token is missing, reordered, aliased, replaced or spurious."""
    expected=rows_for_graph(graph)
    source=rows
    if require_header:
        if tuple(str(x) for x in rows[0]) != COLUMNS:
            raise ValueError("PASIGRAPHY_SPREADSHEET_HEADER_DRIFT")
        source=rows[1:]
    if len(source)!=len(expected):
        raise ValueError("PASIGRAPHY_SPREADSHEET_TOKEN_COUNT_MISMATCH")
    for i,(actual,reference) in enumerate(zip(source,expected)):
        if len(actual)!=len(COLUMNS) or [str(x) for x in actual]!=reference:
            raise ValueError(f"PASIGRAPHY_SPREADSHEET_TOKEN_ROW_DRIFT:{i}")
    return {"schema":SCHEMA,"source_graph_digest":digest(graph),
            "mapped_tokens":len(expected),"unique_semantic_identities":len(expected),
            "registry_sheet":REGISTRY_SHEET,"exact_order_and_semantics":True,
            "ni_compliance_claimed":False,"new_token_learning_claimed":False}


def read_historic_graph(path:Path)->dict:
    import torch
    p=Path(path).resolve(strict=True)
    if digest_file(p)!=AUDITED_PARENT.sha256:
        raise ValueError("PASIGRAPHY_ORIGINAL_CHECKPOINT_SHA_CHANGED")
    payload=torch.load(p,map_location="cpu",weights_only=True)
    graph=payload["graph"]
    if digest(graph)!=ORIGINAL_GRAPH_DIGEST or len(graph["tokens"])!=222:
        raise ValueError("PASIGRAPHY_LEGACY_GRAPH_DRIFT")
    if payload["config"]["vocab_size"]!=len(graph["tokens"]):
        raise ValueError("PASIGRAPHY_MODEL_TOKEN_COUNT_DRIFT")
    validate_one_to_one(graph)
    return graph


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint",required=True,type=Path)
    parser.add_argument("--start",type=int,default=0)
    parser.add_argument("--limit",type=int,default=222)
    args=parser.parse_args(argv)
    if args.start<0 or args.limit<1 or args.limit>222:
        parser.error("invalid bounded atlas slice")
    rows=rows_for_graph(read_historic_graph(args.checkpoint))
    print(json.dumps({"schema":SCHEMA,"columns":COLUMNS,"start":args.start,
                      "total":len(rows),"rows":rows[args.start:args.start+args.limit]},
                     ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
