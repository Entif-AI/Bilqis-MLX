"""Pure, versioned semantic adjudication, never New Ithkuil wordform certification.

The old token graph and native optimizer are read-only evidence, not a target.
The vC sheet is the input; the vD review is a non-destructive successor view.
"""
from __future__ import annotations

from .paths import REPO_ROOT

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

from .registry_versions import REVIEW_COLUMNS
from .semantics.abi import HISTORICAL_PREFIX_SIZE
from .token_atlas import ORIGINAL_GRAPH_DIGEST, rows_for_graph
from .vocabulary_growth import digest

REVIEW_PATH = (REPO_ROOT / "docs" / "provenance" /
               "NI_SEMANTIC_ADJUDICATION_VD_20261015.json")
PARENT = "mapping-review/20261015-c"
SUCCESSOR = "mapping-review/20261015-d"
DISPOSITIONS = frozenset({
    "APPROVED_QUALIFIED_RELATION",
    "APPROVED_COMPOSITION_STRATEGY",
    "APPROVED_NATIVE_PROTOCOL_FUNCTION",
    "APPROVED_NAMED_REFERENT_STRATEGY",
    "APPROVED_TYPED_FORMAL_ADAPTER",
})


def load_adjudication(path: Path = REVIEW_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_adjudication(document: dict, graph: dict) -> dict:
    """Inspect source-anchored review; do not accept claims of rendered NI grammar."""
    rows = rows_for_graph(graph)
    if (
        document.get("schema") != "bilqis.mlx.ni-adjudication/v1"
        or document.get("version") != SUCCESSOR
        or document.get("parent_version") != PARENT
        or document.get("historical_graph_sha256") != ORIGINAL_GRAPH_DIGEST
        or document.get("ni_wordform_status") != "UNCOMPILED_UNCERTIFIED"
        or not isinstance(document.get("authority_comment_sha256"), str)
        or len(document["authority_comment_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in document["authority_comment_sha256"])
        or len(rows) != HISTORICAL_PREFIX_SIZE
    ):
        raise ValueError("NI_ADJUDICATION_CONTRACT_DRIFT")
    observations = document.get("outcomes")
    if not isinstance(observations, list) or len(observations) != 94:
        raise ValueError("NI_ADJUDICATION_CARDINALITY")
    seen = set()
    for item in observations:
        index = item.get("token_id")
        if (
            type(index) is not int
            or index in seen
            or not 0 <= index < HISTORICAL_PREFIX_SIZE
            or item.get("token_symbol") != rows[index][1]
            or item.get("legacy_identity") != rows[index][2]
            or item.get("historic_catalog_description") != rows[index][3]
            or item.get("disposition") not in DISPOSITIONS
            or item.get("prior_disposition") != "HOLD_SOURCE_OR_GRAMMAR_REVIEW"
            or item.get("ni_form_conformance") != "NOT_COMPILED_OR_TESTED"
            or item.get("approved_version") != SUCCESSOR
            or not item.get("ithkuil_source_url", "").startswith("https://ithkuil.net/")
            or not item.get("authority_reference", "").endswith("6187168824")
            or any(not str(item.get(name, "")).strip() for name in (
                "reviewed_bridge", "source_semantics", "scope_difference",
                "historical_source_locus", "ithkuil_source_locus"
            ))
        ):
            raise ValueError(f"NI_ADJUDICATION_INVALID_ROW:{index}")
        seen.add(index)
    return {
        "schema": document["schema"],
        "review_version": SUCCESSOR,
        "reviewed_token_count": len(seen),
        "disposition_counts": dict(Counter(x["disposition"] for x in observations)),
        "source_graph_unchanged": True,
        "ni_wordform_certified": False,
        "neural_updates": 0,
        "document_digest": digest(document),
        "external_authority_digest_supplied_not_self_authenticated": document["authority_comment_sha256"],
    }


def verify_delegation_receipt(document: dict, *, readback_body: str) -> str:
    """Bind the review to authentic comment bytes supplied by a trusted readback.

    This function verifies bytes against the saved hash; it cannot authenticate
    the source of the supplied bytes or authorize an unrelated action.
    """
    expected = document.get("authority_comment_sha256")
    observed = hashlib.sha256(readback_body.encode("utf-8")).hexdigest()
    if not expected or observed != expected or "carte blanche approval" not in readback_body:
        raise ValueError("NI_DELEGATION_RECEIPT_CONTENT_MISMATCH")
    return observed


def materialize_review_view(document: dict, graph: dict, snapshot: list[list[str]]) -> tuple[list[list[str]], dict]:
    """Apply only 94 previously held crosswalk rows to a *copy* of the vC sheet.

    Leaves review history and all original model token identities intact.
    """
    evidence = inspect_adjudication(document, graph)
    if (not snapshot or list(snapshot[0]) != list(REVIEW_COLUMNS) or
            len(snapshot) != HISTORICAL_PREFIX_SIZE + 1):
        raise ValueError("NI_PARENT_REVIEW_SNAPSHOT_INVALID")
    old = [list(map(str, r)) + [""] * (16 - len(r)) for r in snapshot[1:]]
    if any(len(r) != 16 for r in old):
        raise ValueError("NI_PARENT_REVIEW_SCHEMA_INVALID")
    refs = rows_for_graph(graph)
    by_id = {}
    for row in old:
        token_id = int(row[2])
        if token_id in by_id or not 0 <= token_id < HISTORICAL_PREFIX_SIZE:
            raise ValueError("NI_PARENT_DUPLICATE_TOKEN_ID")
        by_id[token_id] = row
        if row[3:6] != [refs[token_id][1], refs[token_id][2], refs[token_id][3]]:
            raise ValueError(f"NI_PARENT_HISTORICAL_DRIFT:{token_id}")
    if len(by_id) != HISTORICAL_PREFIX_SIZE:
        raise ValueError("NI_PARENT_MISSING_TOKEN")
    changed = copy.deepcopy(old)
    changes_by_id = {int(row[2]): row for row in changed}
    for decision in document["outcomes"]:
        token_id = decision["token_id"]
        row = changes_by_id[token_id]
        if (
            row[12] != "HOLD_SOURCE_OR_GRAMMAR_REVIEW"
            or row[7] != decision["previous_proposal"]
            or row[8] != decision["previous_relation"]
        ):
            raise ValueError(f"NI_PARENT_HOLD_DRIFT:{token_id}")
        row[6] = decision["source_semantics"]
        row[7] = decision["reviewed_bridge"]
        row[8] = decision["disposition"]
        row[9] = decision["ithkuil_source_url"]
        row[10] = decision["ithkuil_source_locus"]
        row[11] = (
            "Historical: " + decision["source_semantics"]
            + " | NI difference: " + decision["scope_difference"]
            + " | Source: " + decision["historical_source_locus"]
            + " | NI wordform NOT certified"
        )
        row[12] = decision["disposition"]
        row[13] = "Delegated AI semantic steward (IPR-0220)"
        row[14] = decision["authority_reference"]
        row[15] = SUCCESSOR
    if any(changed[i][:6] != old[i][:6] for i in range(HISTORICAL_PREFIX_SIZE)):
        raise ValueError("NI_HISTORICAL_IDENTITY_MUTATION")
    return [list(REVIEW_COLUMNS)] + changed, evidence
