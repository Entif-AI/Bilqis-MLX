"""Compact longitudinal curriculum evidence, independent of scrolling rows."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .reference_growth import ReferenceGrowth
from .rows import retained_scores


@dataclass(frozen=True)
class DurableHistory:
    recent: tuple
    retained: tuple
    reference: ReferenceGrowth


class CurriculumHistory:
    """Retain one latest accepted source per measured capability."""

    def __init__(self):
        self.latest = {}
        self.last_accepted = None
        self.ordinal = 0
        self.reference = ReferenceGrowth()

    def observe(self, visit):
        if visit.get("outcome") == "ACCEPTED":
            self.ordinal += 1
            item = (self.ordinal, visit)
            self.last_accepted = item
            for capability in retained_scores(visit):
                self.latest[capability] = item
            self.reference = ReferenceGrowth()
        self.reference.seed_checkpoint(visit)

    def view(self, recent):
        ordered = {ordinal: visit for ordinal, visit in self.latest.values()}
        if self.last_accepted is not None:
            ordinal, visit = self.last_accepted
            ordered[ordinal] = visit
        return DurableHistory(tuple(recent),
                              tuple(ordered[key] for key in sorted(ordered)),
                              deepcopy(self.reference))
