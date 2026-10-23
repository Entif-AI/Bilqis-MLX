"""Small source-oracled B connective replay during candidate admission."""
from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

from bilqis_mlx.generated_assessment import verify_stored_cohort
from bilqis_mlx.grade_b_oracle import (
    _direct_truth, evaluate as grade_b_gold, operand_truth,
)
from bilqis_mlx.live_grade_b import _u7c_pattern_counts


TRUTH_PATTERNS = (
    (False, False),
    (False, True),
    (True, False),
    (True, True),
)
_SOURCE_GOLD_DRIFT = "FRAGILE_PRESERVATION_SOURCE_GOLD_DRIFT"
_COHORT_IDENTITY_DRIFT = "FRAGILE_REPLAY_COHORT_IDENTITY_DRIFT"
_U7C_RUNTIME_SAMPLER = "bilqis.mlx.grade-b-u7c-runtime-sampler/v3"
_DIRECT_BOOLEAN_UNIVERSE = "DIRECT_BOOLEAN_AST"


def _is_direct_u7c_row(row: dict) -> bool:
    record = row.get("record") if isinstance(row, dict) else None
    return (isinstance(record, dict) and record.get("task") == "evaluate" and
            row.get("runtime_sampler") == _U7C_RUNTIME_SAMPLER)


def _preservation_pattern_counts(capability: str, rows, *, each: int) -> dict:
    relevant = [row for row in rows if row.get("capability") == capability]
    if relevant and all(_is_direct_u7c_row(row) for row in relevant):
        try:
            return _u7c_pattern_counts(capability.removeprefix("B."), each)
        except ValueError as exc:
            raise ValueError("FRAGILE_PRESERVATION_U7C_PATTERN_CONTRACT_INVALID") from exc
    if any(_is_direct_u7c_row(row) for row in relevant):
        raise ValueError("FRAGILE_PRESERVATION_MIXED_REPRESENTATION")
    return {pattern: 1 for pattern in TRUTH_PATTERNS}


def _replay_operand_pattern(record: dict) -> list[bool]:
    """Recompute OR/XOR operand truth for historical worlds or direct U7C ASTs."""
    if not isinstance(record, dict):
        raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
    if record.get("task") == "evaluate":
        expression = record.get("expression")
        query = record.get("query")
        assignments = record.get("assignments")
        if (not isinstance(expression, dict) or expression != query or
                not isinstance(assignments, dict)):
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
        args = expression.get("args")
        if not isinstance(args, list) or len(args) != 2:
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
        try:
            return [_direct_truth(arg, assignments) for arg in args]
        except ValueError as exc:
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT") from exc
    if record.get("task") == "micro":
        world = record.get("world")
        query = record.get("query")
        args = query.get("args") if isinstance(query, dict) else None
        if not isinstance(world, dict) or not isinstance(args, list) or len(args) != 2:
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
        try:
            return [operand_truth(world, arg) for arg in args]
        except ValueError as exc:
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT") from exc
    raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")


def _operand_kind(node: dict) -> str:
    kind = node.get("kind")
    if kind == "compare":
        value = node.get("operator")
    elif kind == "relation":
        value = node.get("name")
    else:
        value = kind
    if not isinstance(value, str) or not value:
        raise ValueError("FRAGILE_PRESERVATION_OPERAND_KIND_INVALID")
    return value


def structural_signature(row: dict) -> tuple:
    """Describe the compositional shape that truth-pattern-only replay misses."""
    capability = row.get("capability")
    raw = row.get("operand_truths")
    record = row.get("record") or {}
    query = record.get("query") or {}
    args = query.get("args")
    universe = (_DIRECT_BOOLEAN_UNIVERSE if _is_direct_u7c_row(row)
                else row.get("universe_size"))
    if (not isinstance(capability, str) or not capability or
            not isinstance(raw, (list, tuple)) or len(raw) != 2 or
            any(type(value) is not bool for value in raw) or
            not isinstance(args, list) or len(args) != 2 or
            (universe != _DIRECT_BOOLEAN_UNIVERSE and
             (type(universe) is not int or universe < 1))):
        raise ValueError("FRAGILE_PRESERVATION_STRUCTURAL_SIGNATURE_INVALID")
    return (capability, tuple(raw), tuple(_operand_kind(arg) for arg in args),
            universe)


def select_structural_preservation_rows(rows, fixed_rows, *, excluded_ids=frozenset(),
                                        rotation: int, limit: int) -> tuple[dict, ...]:
    """Prefer fresh siblings nearest to rotated fixed structural signatures.

    Structural rehearsal is guidance, not an admission gate. Prefer exact
    signature matches, then same truth-pattern/operand-kind matches across
    universe sizes, then the same truth pattern. Missing shapes simply yield
    fewer rows so callers can fall back to generic truth-table rehearsal.
    """
    if type(rotation) is not int or rotation < 0 or type(limit) is not int or limit < 1:
        raise ValueError("FRAGILE_PRESERVATION_ROTATION_INVALID")
    excluded = set(excluded_ids)
    direct_fixed = tuple(row for row in fixed_rows if _is_direct_u7c_row(row))
    if direct_fixed:
        if len(direct_fixed) != len(tuple(fixed_rows)):
            raise ValueError("FRAGILE_PRESERVATION_MIXED_REPRESENTATION")
        capabilities = {row.get("capability") for row in direct_fixed}
        if len(capabilities) != 1 or limit < 4 or limit % 2:
            raise ValueError("FRAGILE_PRESERVATION_U7C_STRUCTURAL_REQUEST_INVALID")
        capability = next(iter(capabilities))
        required = _preservation_pattern_counts(
            capability, direct_fixed, each=limit)
        desired = []
        for pattern, count in sorted(required.items()):
            signatures = sorted({
                structural_signature(row) for row in direct_fixed
                if tuple(row.get("operand_truths") or ()) == pattern
            })
            if not signatures:
                return ()
            shift = rotation % len(signatures)
            ordered = signatures[shift:] + signatures[:shift]
            desired.extend(ordered[index % len(ordered)] for index in range(count))
        candidates = []
        for row in rows:
            if row.get("id") in excluded or not _is_direct_u7c_row(row):
                continue
            try:
                signature = structural_signature(row)
            except ValueError:
                continue
            candidates.append((row, signature))
        selected, used = [], set()
        for wanted in desired:
            chosen = next((
                row for row, signature in candidates
                if row["id"] not in used and signature == wanted
            ), None)
            if chosen is None:
                chosen = next((
                    row for row, signature in candidates
                    if row["id"] not in used and signature[:3] == wanted[:3]
                ), None)
            if chosen is None:
                chosen = next((
                    row for row, signature in candidates
                    if row["id"] not in used and signature[:2] == wanted[:2]
                ), None)
            if chosen is None:
                return ()
            selected.append(chosen)
            used.add(chosen["id"])
        return tuple(selected)
    desired = sorted({structural_signature(row) for row in fixed_rows})
    if not desired:
        return ()
    shift = rotation % len(desired)
    desired = (desired[shift:] + desired[:shift])[:min(limit, len(desired))]
    candidates = []
    for row in rows:
        if row.get("id") in excluded:
            continue
        try:
            signature = structural_signature(row)
        except ValueError:
            continue
        candidates.append((row, signature))
    selected, used = [], set()
    for wanted in desired:
        chosen = next((
            row for row, signature in candidates
            if row["id"] not in used and signature == wanted
        ), None)
        if chosen is None:
            chosen = next((
                row for row, signature in candidates
                if row["id"] not in used and signature[:3] == wanted[:3]
            ), None)
        if chosen is None:
            chosen = next((
                row for row, signature in candidates
                if row["id"] not in used and signature[:2] == wanted[:2]
            ), None)
        if chosen is not None:
            selected.append(chosen)
            used.add(chosen["id"])
    return tuple(selected)


def select_preservation_rows(rows, *, capabilities=None,
                             excluded_ids=frozenset()) -> tuple[dict, ...]:
    """Pick fresh source siblings that cover each fragile truth-table cell once.

    Fixed examination identities are explicitly excluded. The rehearsal signal
    therefore teaches the same Boolean semantics without turning admission
    questions into lesson material.
    """
    requested = (
        tuple(capabilities) if capabilities is not None else
        tuple(sorted({
            row.get("capability") for row in rows
            if isinstance(row.get("capability"), str) and
            isinstance(row.get("operand_truths"), (list, tuple)) and
            len(row.get("operand_truths")) == 2
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
        required = _preservation_pattern_counts(capability, candidates, each=4)
        by_pattern = {}
        gold_by_pattern = {}
        for row in candidates:
            raw = row.get("operand_truths")
            if (not isinstance(raw, (list, tuple)) or len(raw) != 2 or
                    any(type(value) is not bool for value in raw)):
                raise ValueError("FRAGILE_PRESERVATION_OPERAND_PATTERN_INVALID")
            pattern = tuple(raw)
            gold = row.get("gold")
            if pattern not in TRUTH_PATTERNS or gold not in ("TRUE", "FALSE"):
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


def load_replay_rows(run_dir: Path, receipt: dict, *, capabilities) -> tuple[dict, ...]:
    """Reuse the current materialized full-exam B cases, never generate new gold."""
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
            pattern = _replay_operand_pattern(row["record"])
            if (row.get("operand_truths") != pattern or
                    grade_b_gold(row["record"], name) != row["gold"] or
                    not row.get("tokens")):
                raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
            observed_patterns[tuple(pattern)] += 1
        required = _preservation_pattern_counts(name, group, each=expected)
        if all(_is_direct_u7c_row(row) for row in group):
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
        if old not in ("TRUE", "FALSE") or new not in ("TRUE", "FALSE"):
            raise ValueError("FRAGILE_REPLAY_INVALID_PREDICTION")
        if old == gold and new != gold:
            lost.append({"id": row["id"], "capability": row["capability"]})
        elif old != gold and new == gold:
            repaired += 1
    return {"status": "MEASURED", "cohort_sha256": cohort_sha,
            "rows": len(rows), "regressions": lost, "repaired": repaired}
