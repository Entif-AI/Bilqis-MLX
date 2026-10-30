"""Shared Atlas feature constants and deterministic category encoding."""
from __future__ import annotations
import hashlib
import math
import re

from ...errors import ErrorBus, SEMANTIC_FRAME
from rdflib.namespace import SKOS
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES


# The source owner must attest each selected rule family.
FEATURE_SCHEMA = "bilqis.atlas-feature-schema/v2"
FEATURE_MANIFEST_SCHEMA = "bilqis.atlas-features/v2"
FEATURE_CONCEPT_SCHEMA = "bilqis.atlas-concept-feature/v2"
FEATURE_ROW_SCHEMA = "bilqis.atlas-feature-row/v2"
PROSPECTIVE_IDENTITY_SCHEMA = "bilqis.atlas-prospective-identity-feature/v1"
PROSPECTIVE_FEATURE_SET_SCHEMA = "bilqis.atlas-prospective-identity-feature-set/v1"
FACTOR_ROWS = 512
FIRST_FACTOR_ROW = 2
FACTOR_DIM = 128
GRAPH_DIM = 64
GRAPH_HASH_START = 8
GRAPH_HASH_WIDTH = 56
GRAPH_SIGN_BYTE_INDEX = 8
EDGE_TARGET_INDEX = 2
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_BROADER = SEMANTIC_PREDICATES["subsumption"]
_NARROWER = SEMANTIC_PREDICATES["inverse_subsumption"]
_ROOT_SENSE = Identity("term", ("hasSense",)).iri
_ADMITTED_GRAPH_PREDICATES = frozenset({
    *SEMANTIC_PREDICATES.values(), str(SKOS.member), str(SKOS.memberList),
    _ROOT_SENSE,
})


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<atlas-feature>", span_start=0, span_end=0,
    )


def _utf8(value: str) -> bytes:
    return value.encode("utf-8")


def _sorted_ids(values) -> tuple[str, ...]:
    if any(not isinstance(item, str) or not item for item in values):
        _invalid("BAMF_FEATURE_CATEGORY_INVALID")
    return tuple(sorted(set(values), key=_utf8))


def _factor_overflow(kind: str, identifier: str) -> tuple[float, ...]:
    """f128 exact SHA-256 byte expansion, never a replacement identity."""
    material = b"".join(
        hashlib.sha256(
            ("bamf.factor.v2|" + kind + "|" + identifier + "|" + str(block))
            .encode("utf-8")
        ).digest()
        for block in range(4)
    )
    return tuple((byte / 127.5 - 1.0) / math.sqrt(FACTOR_DIM)
                 for byte in material)


def _category_map(
    values: tuple[str, ...],
    prior: tuple[tuple[str, int], ...] | None,
) -> tuple[tuple[str, int], ...]:
    mapping = dict(prior or (("UNKNOWN", 0), ("NONE", 1)))
    if mapping.get("UNKNOWN") != 0 or mapping.get("NONE") != 1:
        _invalid("BAMF_FEATURE_RESERVED_CATEGORY_DRIFT")
    used = {row for row in mapping.values() if row >= FIRST_FACTOR_ROW}
    if (len(used) != sum(row >= FIRST_FACTOR_ROW for row in mapping.values())
            or any(type(row) is not int or not 0 <= row < FACTOR_ROWS
                   for row in mapping.values())):
        _invalid("BAMF_FEATURE_PRIOR_MAP_INVALID")
    next_row = max(used, default=FIRST_FACTOR_ROW - 1) + 1
    for identifier in _sorted_ids(values):
        if identifier in ("UNKNOWN", "NONE"):
            _invalid("BAMF_FEATURE_RESERVED_ID_COLLISION")
        if identifier in mapping:
            continue
        mapping[identifier] = next_row if next_row < FACTOR_ROWS else 0
        if next_row < FACTOR_ROWS:
            next_row += 1
    return tuple(sorted(mapping.items(), key=lambda item: _utf8(item[0])))


def _normalized_count(count: int) -> float:
    if type(count) is not int or count < 0:
        _invalid("BAMF_FEATURE_SOURCE_COUNT_INVALID")
    return min(math.log1p(count) / math.log(1025), 1.0)
