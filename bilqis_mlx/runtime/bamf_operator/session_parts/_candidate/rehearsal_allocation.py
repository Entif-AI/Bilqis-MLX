"""Reserve balanced predicate rehearsal within the logical instruction budget."""
from collections import Counter
from dataclasses import replace
import math


PREDICATE_PAIR_ROWS = 2
MINIMUM_PRIMARY_ROWS = 2 * PREDICATE_PAIR_ROWS
MINIMUM_LESSON_ROWS = 2 * MINIMUM_PRIMARY_ROWS


def _pressure(teacher, capability, scope, protected):
    losses = dict.fromkeys(protected, 0.0)
    for event in teacher.get("causal_experiment", {}).get("negative_archetypes", ()):
        if (event.get("capability") != capability
                or event.get("curriculum_scope") != scope):
            continue
        # Historical peer deltas are comparable; never treat historical
        # active-target gains as fixed-reference safety measurements.
        deltas = event.get("fixed_reference_deltas", event.get("delta", {}))
        for peer in losses:
            value = deltas.get(peer)
            if type(value) in (float, int) and math.isfinite(value) and -1 <= value < 0:
                losses[peer] -= value
    return losses


def _predicate_geometry(geometry):
    return (geometry is not None and geometry.layout == "singleton"
            and geometry.provider == "predicate")


def reserve_preservation(source_context, offer, pool, protection, target, teacher, scope,
                         *, geometry_for_capability):
    """Adapt reservation only where admitted sources support balanced singleton draws.

    Multi-view construction geometry is not interchangeable with binary
    predicate pairs. Leave those complete lessons unchanged.
    """
    protected = tuple(sorted(target.protected_capability_ids))
    total = offer.source_each
    if (not protected or total < MINIMUM_LESSON_ROWS or total % PREDICATE_PAIR_ROWS
            or not _predicate_geometry(geometry_for_capability(source_context, offer.capability_id))
            or any(not _predicate_geometry(geometry_for_capability(source_context, cap))
                   for cap in protected)):
        return pool, None
    baseline = pool.baseline
    if (len(baseline) != total or any(len(group.rows) != 1 for group in baseline)
            or len({group.stratum for group in baseline}) != PREDICATE_PAIR_ROWS):
        return pool, None
    counts = Counter(group.rows[0]["gold"] for group in baseline)
    if counts != {"TRUE": total // PREDICATE_PAIR_ROWS, "FALSE": total // PREDICATE_PAIR_ROWS}:
        return pool, None
    pressure = _pressure(teacher, offer.capability_id, scope, protected)
    # Reserve at least the previous peer-row budget, rounded to pairs.
    # Each distinct measured interference adds one pair, bounded to half
    # the primary budget. This is a prospective pedagogical allocation,
    # not a change to retention thresholds or scope.
    pair_budget = min(total // MINIMUM_PRIMARY_ROWS, (len(protected) + 1) // PREDICATE_PAIR_ROWS
                      + sum(loss > 0 for loss in pressure.values()))
    primary = total - PREDICATE_PAIR_ROWS * pair_budget
    remaining = {"TRUE": primary // PREDICATE_PAIR_ROWS, "FALSE": primary // PREDICATE_PAIR_ROWS}
    groups = []
    for group in baseline:
        gold = group.rows[0]["gold"]
        if remaining[gold]:
            groups.append(group)
            remaining[gold] -= 1
    return replace(pool, baseline=tuple(groups)), {
        "schema": "bilqis.bamf.predicate-preservation-allocation/v1",
        "protection_plan_sha256": protection.digest,
        "primary_rows": primary, "reserved_rows": PREDICATE_PAIR_ROWS * pair_budget,
        "pressure": pressure,
    }


def valid_allocation(allocation, protection_digest, protected, primary):
    if not isinstance(allocation, dict):
        return False
    reserved = allocation.get("reserved_rows")
    pressure = allocation.get("pressure")
    return (
        allocation.get("schema") == "bilqis.bamf.predicate-preservation-allocation/v1"
        and allocation.get("protection_plan_sha256") == protection_digest
        and allocation.get("primary_rows") == primary
        and type(reserved) is int and 0 < reserved <= primary and reserved % PREDICATE_PAIR_ROWS == 0
        and type(primary) is int and primary >= MINIMUM_PRIMARY_ROWS and primary % PREDICATE_PAIR_ROWS == 0
        and isinstance(pressure, dict) and bool(pressure)
        and set(pressure) == set(protected)
        and all(type(value) in (float, int) and math.isfinite(value) and value >= 0
                for value in pressure.values())
    )


def scheduled_pairs(allocation, ordinal, rotation):
    """Rotate minimum exposure, then distribute spare capacity by measured loss."""
    pressure = allocation["pressure"]
    names = sorted(pressure)
    offset = rotation % len(names)
    names = names[offset:] + names[:offset]
    weights = {cap: 1.0 + pressure[cap] for cap in names}
    total_weight = sum(weights.values())
    credits = dict.fromkeys(names, 0.0)
    pair_budget = allocation["reserved_rows"] // PREDICATE_PAIR_ROWS
    for step in range(ordinal):
        choices = [names[step % len(names)]]
        for _ in range(pair_budget - 1):
            for cap in names:
                credits[cap] += weights[cap]
            cap = max(names, key=credits.__getitem__)
            credits[cap] -= total_weight
            choices.append(cap)
    return Counter(choices)
