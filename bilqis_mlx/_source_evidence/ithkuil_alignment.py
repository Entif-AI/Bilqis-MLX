"""Research-only New Ithkuil semantic bridges; never remap legacy neural IDs.

Bridge records are prospective, with explicit non-equivalence and prerequisite
status. Their presence cannot make an examination legal or qualify a grade.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Relation = Literal["exact", "partial", "analogy", "unverified"]


@dataclass(frozen=True)
class Bridge:
    bridge_id: str
    source_chapter: str
    ithkuil_concept: str
    legacy_concepts: tuple[str, ...]
    relation: Relation
    prerequisite_semantics: tuple[str, ...]
    not_equivalent_to: tuple[str, ...]
    source_url: str
    status: str = "RESEARCH_SEED_NOT_TAUGHT"


CH3 = "https://www.ithkuil.net/newithkuil_03_morphology.htm"
CH13 = "https://www.ithkuil.net/newithkuil_13_numbers.htm"

BRIDGES: tuple[Bridge, ...] = (
    Bridge("NI-C3-001", "New Ithkuil Ch.3 3.1", "Configuration",
           ("G11", "G12", "G15", "G19"), "partial",
           ("plexity", "separability", "similarity", "finite entity groups"),
           ("set cardinality alone", "graph reachability alone"), CH3),
    Bridge("NI-C3-002", "New Ithkuil Ch.3 3.1", "Plexity",
           ("G19",), "partial", ("one-to-one correspondence", "count sequence", "cardinality"),
           ("ordinary cardinality in every context",), CH3),
    Bridge("NI-C3-003", "New Ithkuil Ch.3 3.1", "Similarity",
           ("G05", "G11", "G12", "G21"), "analogy", ("typed attributes", "fuzzy similarity"),
           ("strict equality",), CH3),
    Bridge("NI-C3-004", "New Ithkuil Ch.3 3.1", "Separability",
           ("G04", "G05", "G15"), "analogy", ("identity", "separate", "connected", "fused"),
           ("graph edge implies fusion",), CH3),
    Bridge("NI-C3-005", "New Ithkuil Ch.3 3.2", "Affiliation",
           ("G13", "G14", "G15"), "analogy", ("purpose roles", "group function"),
           ("physical co-occurrence",), CH3),
    Bridge("NI-C3-006", "New Ithkuil Ch.3 3.3", "Perspective",
           ("G06", "G07", "G11", "G19"), "analogy", ("semantic frame", "quantified reference"),
           ("monadic means exactly one",), CH3),
    Bridge("NI-N13-001", "New Ithkuil Ch.13 13.0-13.2", "Centesimal numbers",
           ("G19", "G20", "G21", "G22"), "partial",
           ("number identity", "one-to-one mapping", "ordered count", "cardinality above three",
            "root and formative construction"),
           ("decimal number tokens", "cardinality of unintroduced objects"), CH13),
)


def validate_bridges(bridges: tuple[Bridge, ...] = BRIDGES) -> None:
    if len(set(b.bridge_id for b in bridges)) != len(bridges):
        raise ValueError("DUPLICATE_ITHKUIL_BRIDGE_ID")
    for bridge in bridges:
        if (not bridge.bridge_id or bridge.relation not in ("exact", "partial", "analogy", "unverified")
                or not bridge.ithkuil_concept or not bridge.source_url.startswith("https://www.ithkuil.net/")
                or not bridge.prerequisite_semantics or not bridge.not_equivalent_to
                or bridge.status != "RESEARCH_SEED_NOT_TAUGHT"):
            raise ValueError("INCOMPLETE_OR_PREMATURE_ITHKUIL_BRIDGE")
        if not all(x.startswith(("G", "B")) for x in bridge.legacy_concepts):
            raise ValueError("BRIDGE_LEGACY_ALIAS_INVALID")


def approved_training_bridges(*, passed_prerequisites: frozenset[str]) -> tuple[Bridge, ...]:
    """Research records alone cannot provide a new executable lesson compiler."""
    validate_bridges()
    return ()
