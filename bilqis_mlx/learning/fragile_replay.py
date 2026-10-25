"""Cohort custody and source-guided replay during candidate admission."""
from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

from bilqis_mlx.generated_assessment import verify_stored_cohort
from bilqis_mlx.profiles.retention import fragile_preservation_policy
from bilqis_mlx.source_adapters.school import fragile_source_policy


_SOURCE_GOLD_DRIFT = "FRAGILE_PRESERVATION_SOURCE_GOLD_DRIFT"
_COHORT_IDENTITY_DRIFT = "FRAGILE_REPLAY_COHORT_IDENTITY_DRIFT"


def _source_policy():
    return fragile_source_policy(fragile_preservation_policy().source_selector)


def structural_signature(row: dict) -> tuple:
    """Compatibility projection of the source-owned structural signature."""
    return _source_policy().signature(row)


def select_structural_preservation_rows(rows, fixed_rows, *, excluded_ids=frozenset(),
                                        rotation: int, limit: int,
                                        source_policy=None) -> tuple[dict, ...]:
    """Select fresh siblings using the source's ordered structural match keys."""
    source = source_policy if source_policy is not None else _source_policy()
    if type(rotation) is not int or rotation < 0 or type(limit) is not int or limit < 1:
        raise ValueError("FRAGILE_PRESERVATION_ROTATION_INVALID")
    excluded = set(excluded_ids)
    direct_fixed = tuple(row for row in fixed_rows if source.is_exact(row))
    if direct_fixed:
        if len(direct_fixed) != len(tuple(fixed_rows)):
            raise ValueError("FRAGILE_PRESERVATION_MIXED_REPRESENTATION")
        capability = source.structural_capability(direct_fixed, limit)
        required = source.pattern_counts(
            capability, direct_fixed, each=limit)
        desired = []
        for pattern, count in sorted(required.items()):
            signatures = sorted({
                source.signature(row) for row in direct_fixed
                if source.row_pattern(row) == pattern
            })
            if not signatures:
                return ()
            shift = rotation % len(signatures)
            ordered = signatures[shift:] + signatures[:shift]
            desired.extend(ordered[index % len(ordered)] for index in range(count))
        candidates = []
        for row in rows:
            if row.get("id") in excluded or not source.is_exact(row):
                continue
            try:
                signature = source.signature(row)
            except ValueError:
                continue
            candidates.append((row, signature))
        selected, used = [], set()
        for wanted in desired:
            chosen = None
            for level, key in enumerate(source.matching_keys(wanted)):
                chosen = next((row for row, signature in candidates
                    if row["id"] not in used and
                    source.matching_keys(signature)[level] == key), None)
                if chosen is not None:
                    break
            if chosen is None:
                return ()
            selected.append(chosen)
            used.add(chosen["id"])
        return tuple(selected)
    desired = sorted({source.signature(row) for row in fixed_rows})
    if not desired:
        return ()
    shift = rotation % len(desired)
    desired = (desired[shift:] + desired[:shift])[:min(limit, len(desired))]
    candidates = []
    for row in rows:
        if row.get("id") in excluded:
            continue
        try:
            signature = source.signature(row)
        except ValueError:
            continue
        candidates.append((row, signature))
    selected, used = [], set()
    for wanted in desired:
        chosen = None
        for level, key in enumerate(source.matching_keys(wanted)):
            chosen = next((row for row, signature in candidates
                if row["id"] not in used and
                source.matching_keys(signature)[level] == key), None)
            if chosen is not None:
                break
        if chosen is not None:
            selected.append(chosen)
            used.add(chosen["id"])
    return tuple(selected)


def select_preservation_rows(rows, *, capabilities=None,
                             excluded_ids=frozenset(), each=4,
                             source_policy=None) -> tuple[dict, ...]:
    """Select source patterns with stable row-identity exclusions."""
    source = source_policy if source_policy is not None else _source_policy()
    requested = (
        tuple(capabilities) if capabilities is not None else
        tuple(sorted({
            row.get("capability") for row in rows
            if source.eligible(row)
        })))
    if (not requested or len(requested) != len(set(requested)) or
            any(not isinstance(capability, str) or not capability
                for capability in requested)):
        raise ValueError("FRAGILE_PRESERVATION_INVALID_CAPABILITY_SET")
    excluded = set(excluded_ids)
    selected = []
    for capability in requested:
        candidates = [row for row in rows
                      if row.get("capability") == capability and
                      row.get("id") not in excluded]
        required = source.pattern_counts(capability, candidates, each=each)
        by_pattern = {}
        gold_by_pattern = {}
        for row in candidates:
            pattern = source.row_pattern(row)
            gold = row.get("gold")
            if gold not in source.answer_values:
                raise ValueError(_SOURCE_GOLD_DRIFT)
            prior_gold = gold_by_pattern.setdefault(pattern, gold)
            if prior_gold != gold:
                raise ValueError(_SOURCE_GOLD_DRIFT)
            if not row.get("tokens"):
                raise ValueError("FRAGILE_PRESERVATION_SOURCE_TOKENS_MISSING")
            by_pattern.setdefault(pattern, []).append(row)
        for pattern, count in sorted(required.items()):
            available = by_pattern.get(pattern, ())
            if len(available) < count:
                raise ValueError("FRAGILE_PRESERVATION_INCOMPLETE_TRUTH_TABLE")
            selected.extend(available[:count])
    return tuple(selected)


def fresh_preservation_rows(fixed_rows, *, capabilities, draw_rows, seed_for,
                            rotation: int, batch_size: int,
                            retention_policy=None, source_policy=None) -> tuple[dict, ...]:
    """Draw up to three source cohorts and select bounded fresh siblings."""
    policy = retention_policy if retention_policy is not None else fragile_preservation_policy()
    source = (source_policy if source_policy is not None else
              fragile_source_policy(policy.source_selector))
    fixed = tuple(fixed_rows)
    requested = tuple(capabilities)
    if not fixed or not requested:
        return ()
    excluded = {row["id"] for row in fixed}
    target = policy.per_capability_target
    selected = []
    for name in requested:
        fixed_capability = tuple(row for row in fixed if row["capability"] == name)
        fresh = []
        matched = ()
        for attempt in range(3):
            fresh.extend(draw_rows(capability=name, seed=seed_for(name, attempt),
                                   each=max(96, batch_size * 3)))
            matched = select_structural_preservation_rows(
                fresh, fixed_capability, excluded_ids=excluded,
                rotation=rotation, limit=target, source_policy=source)
            if len(matched) >= target:
                break
        delivered = list(matched)
        if len(delivered) < target:
            try:
                fallback = select_preservation_rows(
                    fresh, capabilities=(name,), excluded_ids=excluded,
                    each=target, source_policy=source)
            except ValueError as exc:
                if str(exc) != "FRAGILE_PRESERVATION_INCOMPLETE_TRUTH_TABLE":
                    raise
                fallback = ()
            used = {row["id"] for row in delivered}
            for row in fallback:
                if row["id"] not in used:
                    delivered.append(row)
                    used.add(row["id"])
                if len(delivered) >= target:
                    break
        selected.extend(delivered[:target])
    if any(row["id"] in excluded for row in selected):
        raise ValueError("FRAGILE_PRESERVATION_EXAM_ROW_LEAK")
    return tuple(selected)


def load_replay_rows(run_dir: Path, receipt: dict, *, capabilities) -> tuple[dict, ...]:
    """Read preserved source-checked cases from the current complete exam cohort."""
    requested = tuple(capabilities)
    if (not requested or len(requested) != len(set(requested)) or
            any(not isinstance(name, str) or not name for name in requested)):
        raise ValueError("FRAGILE_REPLAY_CAPABILITY_SET_INVALID")
    exam = receipt.get("last_exam") or {}
    scores = exam.get("scores") or {}
    if any(name not in scores for name in requested):
        return ()
    sha = exam.get("cohort_sha256")
    if (not isinstance(sha, str) or len(sha) != 64 or
            any(c not in "0123456789abcdef" for c in sha) or
            exam.get("cohort_file") != f"cohorts/{sha}.json"):
        raise ValueError("FRAGILE_REPLAY_UNBOUND_EXAM_COHORT")
    file = Path(run_dir) / "cohorts" / f"{sha}.json"
    if file.parent.is_symlink() or file.is_symlink() or not file.is_file():
        raise ValueError("FRAGILE_REPLAY_UNSAFE_COHORT_PATH")
    stored = json.loads(file.read_text(encoding="utf-8"))
    if stored.get("cohort_sha256") != sha:
        raise ValueError(_COHORT_IDENTITY_DRIFT)
    try:
        cohort = verify_stored_cohort(
            stored, sha,
            expected_rubric_sha256=exam.get("rubric_sha256"),
            expected_factory_release_sha256=exam.get(
                "factory_release_sha256"))
    except ValueError as exc:
        if str(exc) == "STORED_COHORT_CONTENT_DRIFT":
            raise ValueError("FRAGILE_REPLAY_COHORT_CONTENT_DRIFT") from exc
        raise ValueError(_COHORT_IDENTITY_DRIFT) from exc
    rows = tuple(row for row in cohort.rows if row["capability"] in requested)
    expected_total = sum(scores[name].get("total", 0) for name in requested)
    if (expected_total < 1 or len(rows) != expected_total or
            len({row["id"] for row in rows}) != expected_total):
        raise ValueError("FRAGILE_REPLAY_INCOMPLETE_B_COHORT")
    for name in requested:
        group = [row for row in rows if row["capability"] == name]
        expected = scores[name].get("total")
        if type(expected) is not int or expected < 4 or len(group) != expected:
            raise ValueError("FRAGILE_REPLAY_INCOMPLETE_B_CAPABILITY")
        observed_patterns = Counter()
        for row in group:
            if not _source_policy().verify_row(row, name):
                raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
            observed_patterns[_source_policy().row_pattern(row)] += 1
        required = _source_policy().pattern_counts(name, group, each=expected)
        if all(_source_policy().is_exact(row) for row in group):
            if observed_patterns != Counter(required):
                raise ValueError("FRAGILE_REPLAY_U7C_PATTERN_DRIFT")
        elif set(observed_patterns) != set(required):
            raise ValueError("FRAGILE_REPLAY_INCOMPLETE_TRUTH_TABLE")
    return rows


def screen_replay(rows: tuple[dict, ...], parent: dict[str, str],
                  candidate: dict[str, str], cohort_sha: str) -> dict:
    """A fixed row lost by a challenger cannot be offset by a different gain."""
    required = {row["id"] for row in rows}
    if required - parent.keys() or required - candidate.keys():
        raise ValueError("FRAGILE_REPLAY_MISSING_PAIRED_PREDICTION")
    lost = []
    repaired = 0
    for row in rows:
        old, new, gold = parent[row["id"]], candidate[row["id"]], row["gold"]
        if old not in _source_policy().answer_values or new not in _source_policy().answer_values:
            raise ValueError("FRAGILE_REPLAY_INVALID_PREDICTION")
        if old == gold and new != gold:
            lost.append({"id": row["id"], "capability": row["capability"]})
        elif old != gold and new == gold:
            repaired += 1
    return {"status": "MEASURED", "cohort_sha256": cohort_sha,
            "rows": len(rows), "regressions": lost, "repaired": repaired}
