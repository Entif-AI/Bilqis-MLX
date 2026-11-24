"""Command-local GREW from retained, comparable reference observations."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .scores import paired_scores
from ..growth_projection import _grew
from bilqis_mlx.data_plane import SHA256_HEX_LENGTH


@dataclass
class ReferenceScore:
    grade: str
    contract: tuple
    start: tuple[int, int]
    latest: tuple[int, int]
    generation: int


class ReferenceGrowth:
    """Track stable reference scores without evaluating any neural weights."""

    def __init__(self):
        self.scores = {}
        self.seen = set()
        self.generation = 0
        self.expected = None
        self.grade_totals = {}
        self.release = None
        self.blocked = set()

    def _measure(self, visit, *, initial=False):
        context = visit.get("reference_context") or {}
        release, rubric = (context.get(key) for key in (
            "factory_release_sha256", "rubric_sha256"))
        if not all(isinstance(key, str) and len(key) == SHA256_HEX_LENGTH for key in (release, rubric)):
            return
        if self.release is not None and self.release != release:
            # A new release is not a comparable command-start baseline.
            self.blocked.update(self.scores)
            self.scores.clear()
            self.grade_totals.clear()
        self.release = release
        total = context.get("total_capabilities")
        if type(total) is int and total > 0:
            self.expected = total
        coverage = (visit.get("visit_evidence") or {}).get("baseline_coverage") or {}
        groups = coverage.get("group_denominators") if isinstance(coverage, dict) else None
        for item in groups if isinstance(groups, (list, tuple)) else ():
            if isinstance(item, dict) and isinstance(item.get("group"), str):
                count = item.get("total")
                if type(count) is int and count > 0:
                    owner = item["group"]
                    self.grade_totals[owner] = max(count, self.grade_totals.get(owner, 0))
        accepted = visit.get("outcome") == "ACCEPTED"
        target = visit.get("capability_id")
        explicit = visit.get("fixed_reference_scores")
        if explicit is not None:
            census = visit.get("fixed_reference_cohort_sha256")
            if not isinstance(census, str) or len(census) != SHA256_HEX_LENGTH:
                return
            scores = paired_scores({"paired_scores": explicit})
        else:
            protected = visit.get("protected_capabilities")
            if not isinstance(protected, list):
                return
            # Historical ordinary C05 redraws the target but keeps peer rows stable.
            scores = {cap: pair for cap, pair in paired_scores(visit).items()
                      if cap != target and cap in protected}
        for cap, (before, after, denominator) in scores.items():
            if cap in self.blocked:
                continue
            owner = context.get("grade") if cap == target else cap.partition(".")[0]
            if not isinstance(owner, str) or not owner:
                continue
            contract = (release, rubric, denominator)
            old = self.scores.get(cap)
            current = (after if accepted else before, denominator)
            previous_generation = self.generation - int(accepted and not initial)
            if old is not None:
                observed_parent = current if initial else (before, denominator)
                if (old.contract != contract
                        or (old.generation == previous_generation
                            and old.latest != observed_parent)):
                    # Do not manufacture growth across incompatible evidence.
                    self.scores.pop(cap)
                    self.blocked.add(cap)
                    continue
                old.latest, old.generation = current, self.generation
            elif initial or previous_generation == 0:
                baseline = current if initial else (before, denominator)
                self.scores[cap] = ReferenceScore(
                    owner, contract, baseline, current, self.generation)

    def prime(self, visits):
        """Read the last retained checkpoint and later rejected parent observations."""
        if self.seen or self.scores:
            return
        durable = [v for v in visits if v.get("_durable_terminal_history")]
        last = max((i for i, v in enumerate(durable)
                    if v.get("outcome") == "ACCEPTED"), default=0)
        for visit in durable[last:]:
            self._measure(visit, initial=True)

    def observe(self, visit):
        if not visit or not visit.get("_durable_terminal_history"):
            return
        identity = visit.get("visit_id") or visit.get("observation_id")
        if not identity or identity in self.seen:
            return
        self.seen.add(identity)
        if visit.get("outcome") == "ACCEPTED":
            self.generation += 1
        self._measure(visit)

    def publish(self, board):
        values = [_grew(item.start, item.latest) for item in self.scores.values()]
        stale = sum(item.generation != self.generation for item in self.scores.values())
        count = len(values)
        partial = bool(stale or self.expected is None or count != self.expected)
        board.state.update(
            grew=round(sum(values) / count) if count else None,
            _bamf_growth_partial=partial,
            _bamf_growth_coverage=(count, self.expected, stale),
        )

    def apply_rows(self, summaries, families):
        by_grade = defaultdict(list)
        for cap, item in self.scores.items():
            by_grade[item.grade].append(item)
        for row in families:
            item = self.scores.get(row.get("family"))
            if item is None:
                continue
            row.update(start=f"{item.start[0]}/{item.start[1]}",
                       after=f"{item.latest[0]}/{item.latest[1]}",
                       outcome="REF STALE" if item.generation != self.generation else "REF")
        for row in summaries:
            owner = row.get("grade")
            items = by_grade.get(owner, ())
            if not items:
                # A last-pair score is not longitudinal command growth.
                row["_bamf_no_growth_baseline"] = True
                continue
            total = sum(item.latest[1] for item in items)
            stale = sum(item.generation != self.generation for item in items)
            # A grade's measured local scope need not be its entire curriculum.
            count = len(items)
            expected = (self.grade_totals.get(owner)
                        if sum(self.grade_totals.values()) == self.expected else None)
            if expected is None:
                label = f"REF {count}/?"
            else:
                label = f"REF {count}/{expected}"
            if stale:
                label += f" S{stale}"
            row.update(
                start=f"{sum(item.start[0] for item in items)}/{total}",
                latest=f"{sum(item.latest[0] for item in items)}/{total}",
                outcome=label,
            )
