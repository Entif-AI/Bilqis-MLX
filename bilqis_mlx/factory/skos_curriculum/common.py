"""Source-family schema constants, digest and source-pin access."""
from __future__ import annotations
import hashlib
import json
import re
from bilqis_mlx.errors import ErrorBus, SCHOOL
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES

FAMILY_INVENTORY_SCHEMA = "bilqis.semantic-family-inventory-proposal/v1"
FAMILY_OBLIGATION_SCHEMA = "bilqis.semantic-family-obligation/v1"
FAMILY_CONCEPT_SCHEMA = "bilqis.semantic-family-concept/v1"
FAMILY_RULE_SCHEMA = "bilqis.semantic-family-source-rule/v1"
CURRICULUM_CANDIDATE_SCHEMA = "bilqis.semantic-curriculum-proposal/v1"
LEARNED_FRONTIER_SCHEMA = "bilqis.semantic-learned-frontier/v1"
SOURCE_LESSON_SCHEMA = "bilqis.source-constructive-lesson-proposal/v1"
SOURCE_LESSON_SET_SCHEMA = "bilqis.source-constructive-lesson-proposal-set/v1"
LEARNING_UNVERIFIED = "LEARNING_UNVERIFIED"
SOURCE_PROJECTION_ONLY = "SOURCE_PROJECTION_NOT_AUTHORITY"
SOURCE_FACT_ARITY = 3
SOURCE_FACT_PREFIX_ARITY = 2
SOURCE_FACT_REF_INDEX = 2
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SEMANTIC_RELATIONS = tuple(sorted(set(SEMANTIC_PREDICATES.values())))
_SOURCE_TABLES = frozenset({
    "atomic/morphemes_atomic",
    "lexicon/lexicon_roots",
    "lexicon/lexicon_root_senses",
    "residue/morpheme_compositions",
    "residue/composition_components",
    "residue/affix_degrees",
    "residue/allomorph_rules",
})
_FORMAL_FAMILIES = frozenset({"boolean", "numeric"})
_FORMAL_ID_PREFIXES = {
    "boolean": ("legacy:cogal.operator.", "urn:formal:boolean:"),
    "numeric": ("bilqis.numeric/v1:school.op.", "urn:formal:numeric:"),
}
_SCOPE_MODALITY_TIME_CATEGORIES = (
    "ASPECT", "CASE_SCOPE", "FUNCTION_SPECIFICATION_CONTEXT",
    "ILLOCUTION", "MOOD", "PHASE", "PERSPECTIVE_ESSENCE",
)


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()



def _load_pinned(atlas):
    from . import load_pinned_atlas_snapshot
    return load_pinned_atlas_snapshot(atlas)
