"""Bounded, source-owned construction search for scored R13 debt."""
from dataclasses import dataclass

from bilqis_mlx.factory._model.weakness import classify_weakness
from bilqis_mlx.runtime.structural_weakness_ledger import _ledger_key
from bilqis_mlx.source_adapters.lesson_geometry import (
    complete_groups, distinct_groups, geometry_for_adapter,
)


_MAX_DRAWS = 16


@dataclass(frozen=True)
class GroupOffer:
    rows: tuple
    matches: tuple[tuple[str, str], ...]  # actual matching row ID, debt key
    parent_rows: tuple
    authority: object
    seed: int


def _occupied(rows):
    return ({row["id"] for row in rows},
            {tuple(row["tokens"]) for row in rows if "tokens" in row})


def choose_groups(offers, ordered_keys, capacity, reserved_rows=()):
    """Allocate whole groups in least-exposed debt order, never split views."""
    used_ids, used_tokens = _occupied(reserved_rows)
    selected, served = [], set()
    remaining = capacity
    for key in ordered_keys:
        if key in served:
            continue
        eligible = []
        for index, offer in enumerate(offers):
            keys = {debt for _, debt in offer.matches}
            if key not in keys or len(offer.rows) > remaining:
                continue
            ids, tokens = _occupied(offer.rows)
            if ids & used_ids or tokens & used_tokens:
                continue
            eligible.append((len(offer.rows), -len(keys - served), index, offer))
        if not eligible:
            continue
        _, _, _, chosen = min(eligible, key=lambda item: item[:3])
        selected.append(chosen)
        ids, tokens = _occupied(chosen.rows)
        used_ids.update(ids)
        used_tokens.update(tokens)
        served.update(debt for _, debt in chosen.matches)
        remaining -= len(chosen.rows)
    return tuple(selected), served, remaining


def _draw_size(geometry, minimum):
    if geometry.layout == "numeric":
        return ((minimum + 2) // 3) * 3
    if geometry.layout == "copular":
        return 12
    return minimum


def _group_offers(rows, authority, seed, geometry, execution, adapter, admitted, debts):
    result = []
    for group in distinct_groups(complete_groups(rows, geometry)):
        matches = []
        for row in group.rows:
            classified = classify_weakness(
                adapter, execution, row, provider_descriptor=admitted)
            if classified is None:
                continue
            debt = debts.get(classified.class_sha256)
            if debt is None or row["id"] in debt["historical_source_ids"]:
                continue
            matches.append((row["id"], _ledger_key(debt)))
        if matches:
            result.append(GroupOffer(group.rows, tuple(matches), rows, authority, seed))
    return result


def targeted_groups(source_context, plan, ordinal, seed_for, minimum, *,
                    reserved_rows=(), exposure_counts=None):
    """Search each bounded draw for every class, including rare/unavailable ones."""
    if not plan.weakness_records:
        return (), ()
    from bilqis_mlx.runtime.structural_weakness_capture import _provider_for_context
    from bilqis_mlx.runtime.priority_lesson import _capacity_failure

    execution, adapter, admitted = _provider_for_context(
        source_context, plan.target_capability_id)
    debts = {record["weakness_class"]["class_sha256"]: record
             for record in plan.weakness_records}
    counts = dict(plan.weakness_exposures if exposure_counts is None else exposure_counts)
    ordered = tuple(sorted((_ledger_key(record) for record in debts.values()),
                           key=lambda key: (counts.get(key, 0), key)))
    geometry = geometry_for_adapter(adapter)
    if geometry is None:
        return (), tuple((key, "UNSUPPORTED_GEOMETRY") for key in ordered)
    capacity = plan.weakness_capacity
    each = _draw_size(geometry, minimum)
    if capacity < (3 if geometry.layout == "numeric" else 1):
        return (), tuple((key, "CAPACITY_OR_COLLISION") for key in ordered)
    offers = []
    selected, served, remaining = (), set(), capacity
    for attempt in range(_MAX_DRAWS):
        seed = seed_for(plan, "preservation", plan.target_capability_id,
                        ordinal * _MAX_DRAWS + attempt)
        try:
            rows, authority = source_context.draw_bound_rows(
                seed=seed, capability=plan.target_capability_id, each=each)
        except ValueError as error:
            if _capacity_failure(error, geometry, plan.target_capability_id):
                continue
            raise
        rows = tuple(rows)
        if (len(rows) != each or any(
                row.get("capability") != plan.target_capability_id for row in rows)):
            raise ValueError("BAMF_REHEARSAL_SOURCE_DRAW_INVALID")
        offers.extend(_group_offers(
            rows, authority, seed, geometry, execution, adapter, admitted, debts))
        selected, served, remaining = choose_groups(
            offers, ordered, capacity, reserved_rows)
        if len(served) == len(ordered):
            break
        # A full allocation of the highest-priority prefix needs no more draws.
        # Otherwise keep searching: an unavailable low-exposure class cannot
        # consume other classes' opportunities, because every draw serves all.
        if remaining == 0 and served == set(ordered[:len(served)]):
            break
    available = {key for offer in offers for _, key in offer.matches}
    unavailable = tuple(
        (key, "CAPACITY_OR_COLLISION" if key in available else "NO_MATCH_IN_BUDGET")
        for key in ordered if key not in served)
    return selected, unavailable


def delivered_weakness_controls(source_context, capability, preservation, bindings):
    """Attribute only matching delivered rows, not the companion construction views."""
    matched = tuple((row, bindings[row["id"]].get("weakness_debt_key"))
                    for row in preservation
                    if bindings[row["id"]].get("weakness_debt_key") is not None)
    if not matched:
        return {}
    from bilqis_mlx.runtime.structural_weakness_capture import _provider_for_context

    execution, adapter, admitted = _provider_for_context(source_context, capability)
    facts = {}
    for row, key in matched:
        classified = classify_weakness(
            adapter, execution, row, provider_descriptor=admitted)
        if (not isinstance(key, str) or classified is None
                or key.rsplit(":", 1)[-1] != classified.class_sha256
                or row.get("capability") != capability):
            raise ValueError("BAMF_WEAKNESS_DELIVERED_CLASS_DRIFT")
        facts.setdefault(key, []).append(row["id"])
    count = sum(map(len, facts.values()))
    return {"weakness_class_matches": facts, "weakness_targets_delivered": count,
            "priority_weakness_targets_delivered": count}
