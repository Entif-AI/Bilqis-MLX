"""Literal AtlasFeatures/v2 factor and graph witnesses."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import math
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_features import (
    FACTOR_DIM, FACTOR_ROWS, GRAPH_DIM, FeatureSchema,
    _category_map, build_feature_manifest, plan_prospective_identity_features,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasConcept, AtlasCounts, AtlasRealization,
    CorpusCoverageRow, FrozenAtlasConcept, FrozenAtlasRelation,
    FrozenAtlasSnapshot, SourceRecordRef,
)
from bilqis_mlx.semantics.frame_schema import ConceptRef
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES
from lib.ithkuil.src.skos.identity import Identity


RELEASE = "a" * 64
SOURCE_BUNDLE = "b" * 64
BROADER = SEMANTIC_PREDICATES["subsumption"]
NARROWER = SEMANTIC_PREDICATES["inverse_subsumption"]
ROOT_SENSE = Identity("term", ("hasSense",)).iri
SYMBOLS = {
    "urn:concept:A": ("cogal.operator.AND", 11),
    "urn:concept:B": ("cogal.operator.OR", 12),
}
OVERFLOW_GOLDEN_HEX = {
    "urn:type:0510": (
        "2a72c33e6a305a921f3da649e5ae39aa5799016cab3d955ded8959c8b90bf525"
        "765dfe780ca174d3b67aeba534dcba80f1675fb6e45a81c252f03ad30645bc21"
        "7f4b512d65b663b2836534e8306ee1581eb580481cfc54f1faaf17fece959e1c"
        "82df4834bf623d7b0bf5f7cbedac61a2e8dfd0149442d34b1b658a434c358837"),
    "urn:type:0511": (
        "4cca325d6afe74f661522049ac6de9b00878af32aed3d33c9592d613804ce8c9"
        "27352e1d3dc965a410a6cd24364606498f63cdfe71d1b83db3738dde028a674f"
        "cf55471c7313afde0c414b76b9349d67ce6c4f3ae4558d9d1e8ba69ef4f9f163"
        "c9c5d98d267aa3a357d5d5b2618b927b7a5dac235a9e1881ea76d5d1215a2ad5"),
}


def _snapshot(
    definitions=(("urn:concept:A", ("urn:type:Entity",)),),
    relations=(),
    held=(),
    *,
    release=RELEASE,
    with_source=True,
    forms=(),
    senses=(),
    kinds=(),
):
    entries = tuple(
        AbiEntry(SYMBOLS.get(semantic_id, (semantic_id, index))[1], 0,
                 SYMBOLS.get(semantic_id, (semantic_id, index))[1],
                 semantic_id, SYMBOLS.get(semantic_id, (semantic_id, index))[0],
                 "synthetic:source",
                 True, True, "SOURCE_ADMITTED")
        for index, (semantic_id, _) in enumerate(definitions)
    )
    concepts = tuple(
        FrozenAtlasConcept(
            AtlasConcept(
                semantic_id, dict(kinds).get(semantic_id, "synthetic"), types, (), tuple(
                    AtlasRealization("form:" + str(i))
                    for i in range(dict(forms).get(semantic_id, 0))),
                (), (), tuple(
                    SourceRecordRef("synthetic", "lexicon_root_senses",
                                    "sense:" + str(i))
                    for i in range(dict(senses).get(semantic_id, 0))),
            ),
            entries[index].index, 0, entries[index].index,
            True, "ADMITTED", True, "SOURCE_ADMITTED",
        )
        for index, (semantic_id, types) in enumerate(definitions)
        if with_source
    )
    withheld = tuple(
        CorpusCoverageRow(
            "synthetic", "held", semantic_id, semantic_id,
            "HELD", "HELD", False, "SOURCE_UNRESOLVED",
            "NOT_ADMITTED", "synthetic:owner")
        for semantic_id in held
    )
    return FrozenAtlasSnapshot(
        "bilqis.semantic-atlas-snapshot/v1", "c" * 64, release,
        SOURCE_BUNDLE, "d" * 64, "e" * 64, "f" * 64,
        "0" * 64, "1" * 64, "2" * 64, "3" * 64,
        AtlasCounts(len(entries), len(entries), len(concepts), len(entries),
                    1, len(entries), 0, len(held), 0, 0),
        (), entries, concepts, tuple(
            FrozenAtlasRelation(*edge) for edge in relations),
        withheld, tuple(sorted(
            (entry.semantic_id, entry.index) for entry in entries)),
        tuple(sorted(
            (item.concept.semantic_id, item.abi_index) for item in concepts)),
    )


def _features(snapshot=None, *, roles=("left", "right"),
              schemas=("frame:urn:concept:A",),
              predecessor=None):
    return build_feature_manifest(
        snapshot or _snapshot(),
        FeatureSchema(
            tuple(roles), tuple(schemas), predecessor,
            tuple((schema, "source.micro.boolean-connectives/v1")
                  for schema in sorted(set(schemas)))))


if __name__ == "__main__":
    unittest.main()

class AtlasFeatureTests(unittest.TestCase):
    """Shared test base; behavior cases live beside their owners."""
