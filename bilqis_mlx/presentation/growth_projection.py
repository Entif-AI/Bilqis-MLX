"""Read-only whole-school capability growth projection for the operator dashboard."""
from __future__ import annotations

from collections import defaultdict


def _grew(start: tuple[int, int] | None,
          latest: tuple[int, int] | None) -> int | None:
    if start is None or latest is None or latest[1] <= 0:
        return None
    delta = latest[0] - start[0]
    magnitude = (abs(delta) * 200 + latest[1]) // (2 * latest[1])
    return magnitude if delta > 0 else -magnitude if delta < 0 else 0


class GrowthProjection:
    """Average one GREW vote per active capability, including held-out ones."""

    def __init__(self, active_grades=()):
        self.grades = list(active_grades)
        self.active = defaultdict(set)
        self.start = {}
        self.latest = {}
        self.values = {}

    def _grade(self, grade: str) -> None:
        if grade not in self.grades:
            self.grades.append(grade)

    def begin_execution(self) -> int | None:
        self.start = dict(self.latest)
        self.values = {
            cap: 0 for grade in self.grades for cap in self.active.get(grade, ())
            if cap in self.latest
        }
        return self.average()

    def observe(self, grade: str, capability: str,
                correct: int, total: int) -> int | None:
        self._grade(grade)
        self.active[grade].add(capability)
        latest = (correct, total)
        self.latest[capability] = latest
        baseline = self.start.setdefault(capability, latest)
        self.values[capability] = _grew(baseline, latest)
        return self.average()

    def replace_grade(self, grade: str, old_capabilities,
                      new_capabilities, withheld_capabilities) -> int | None:
        self._grade(grade)
        old = set(old_capabilities)
        active = set(new_capabilities) | set(withheld_capabilities)
        self.active[grade] = active
        for capability in old - active:
            self.start.pop(capability, None)
            self.latest.pop(capability, None)
            self.values.pop(capability, None)
        return self.average()

    def average(self) -> int | None:
        values = [
            self.values[cap]
            for grade in self.grades for cap in sorted(self.active.get(grade, ()))
            if type(self.values.get(cap)) is int
        ]
        return round(sum(values) / len(values)) if values else None
