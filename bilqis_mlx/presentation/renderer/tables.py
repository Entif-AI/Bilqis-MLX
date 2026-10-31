from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Column:
    name: str
    width: int
    key: str
    optional: bool = False
    right: bool = False



TABLES = (
    ("CANDIDATES", (
        Column("GRADE", 5, "grade"), Column("TRY", 4, "attempt", right=True),
        Column("STRATEGY", 9, "strategy", optional=True),
        Column("METHOD", 11, "method", optional=True),
        Column("NUM", 9, "number"), Column("BRIDGE", 9, "bridge"),
        Column("BRG2", 9, "confirm", optional=True),
        Column("OLDpp", 7, "old", right=True),
        Column("REWARD", 8, "reward", right=True),
        Column("DECISION / REASON", 39, "decision"))),
    ("SENTINEL & RETENTION", (
        Column("GRADE", 5, "grade"), Column("TRY", 4, "attempt", right=True),
        Column("PROBEpp", 8, "probe", right=True),
        Column("WORSTpp", 8, "worst", right=True),
        Column("SENTpp", 8, "sent", right=True),
        Column("CEd", 9, "ce", right=True),
        Column("P(C)d", 9, "prob", right=True),
        Column("MARGd", 9, "margin", right=True))),
    ("SOUP & TEACHER", (
        Column("GRADE", 5, "grade"), Column("TRY", 4, "attempt", right=True),
        Column("SOUP_KL", 8, "soup", right=True),
        Column("COVER", 8, "cover", right=True),
        Column("SUP_CE", 8, "sup", right=True),
        Column("PAR_KL", 8, "parent", right=True),
        Column("CREDIT", 9, "credit", right=True),
        Column("BRG_CE", 9, "bridge_ce", right=True))),
    ("BRIDGE FAMILIES", (
        Column("GRADE", 5, "grade"), Column("TRY", 4, "attempt", right=True),
        Column("FAMILY", 18, "family"),
        Column("CORRECT BEFORE", 16, "before",right=True),
        Column("CORRECT AFTER", 16, "after",right=True),
        Column("GAIN", 7, "gain",right=True))),
    ("GRADES & MASTERY", (
        Column("VISIT", 6, "visit", right=True),
        Column("GRADE", 5, "grade"),
        Column("STEP", 7, "step", right=True),
        Column("ELIG", 5, "eligible", right=True),
        Column("PICK", 5, "selected", right=True),
        Column("PREFIX", 6, "prefix", right=True),
        Column("OUTCOME", 29, "outcome"),
        Column("RIGHT%", 6, "right_pct", right=True))),
    ("SYSTEM & QUALIFICATION", (
        Column("TYPE", 14, "kind"),
        Column("GRADE", 5, "grade", optional=True),
        Column("DETAILS", 55, "detail"))),
)

# Full details need about 276 columns. Below that width, the wide view
# preserves three panes but sheds optional metrics; ordinary terminals retain
# the existing vertical presentation. This module is not part of model recipe.

WIDE_MIN_WIDTH = 210

WIDE_MIN_HEIGHT = 12

WIDE_SEP = " | "

WIDE_PANES = (
    ("CANDIDATES",),
    ("SENTINEL & RETENTION", "SOUP & TEACHER", "SYSTEM & QUALIFICATION"),
    ("BRIDGE FAMILIES", "GRADES & MASTERY"),
)

WIDE_ROW_FRACTIONS = {
    # At 36 terminal rows these yield the requested 10/9/4 and 4/8 sections.
    "SENTINEL & RETENTION": .28,
    "SOUP & TEACHER": .25,
    "SYSTEM & QUALIFICATION": .11,
    "BRIDGE FAMILIES": .11,
    "GRADES & MASTERY": .22,
}



Column.__module__ = "bilqis_mlx.presentation.spiral_dashboard"
