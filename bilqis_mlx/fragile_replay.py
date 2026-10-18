"""Small source-oracled B connective replay during candidate admission."""
from __future__ import annotations

import json
from pathlib import Path

from .generated_assessment import make_cohort
from .grade_b_oracle import evaluate as grade_b_gold, operand_truth


CAPABILITIES = ("B.OR", "B.XOR")
TRUTH_PATTERNS = (
    (False, False),
    (False, True),
    (True, False),
    (True, True),
)


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


def _endpoint_topology(args: list[dict]) -> tuple[int, ...]:
    endpoints = []
    for arg in args:
        values = arg.get("args")
        if (not isinstance(values, list) or len(values) != 2 or
                any(item.get("kind") != "entity" or
                    not isinstance(item.get("name"), str)
                    for item in values)):
            raise ValueError("FRAGILE_PRESERVATION_ENDPOINT_TOPOLOGY_INVALID")
        endpoints.extend(item["name"] for item in values)
    aliases, pattern = {}, []
    for name in endpoints:
        aliases.setdefault(name, len(aliases))
        pattern.append(aliases[name])
    return tuple(pattern)


def structural_signature(row: dict) -> tuple:
    """Canonical compositional shape, independent of concrete entity names."""
    capability = row.get("capability")
    truths = row.get("operand_truths")
    query = (row.get("record") or {}).get("query") or {}
    args = query.get("args")
    universe = row.get("universe_size")
    if (capability not in CAPABILITIES or
            not isinstance(truths, (list, tuple)) or len(truths) != 2 or
            any(type(value) is not bool for value in truths) or
            not isinstance(args, list) or len(args) != 2 or
            type(universe) is not int or universe < 1):
        raise ValueError("FRAGILE_PRESERVATION_STRUCTURAL_SIGNATURE_INVALID")
    return (
        capability, tuple(truths),
        tuple(_operand_kind(arg) for arg in args),
        _endpoint_topology(args), universe,
    )


def _signature_schedule(fixed_rows, *, rotation: int, limit: int) -> tuple:
    signatures = sorted({structural_signature(row) for row in fixed_rows})
    if not signatures:
        return ()
    capabilities = {signature[0] for signature in signatures}
    if len(capabilities) != 1:
        raise ValueError("FRAGILE_PRESERVATION_MIXED_CAPABILITY_SIGNATURES")
    capability = next(iter(capabilities))
    quotas = (
        {(False, False): 3, (False, True): 1,
         (True, False): 1, (True, True): 1}
        if capability == "B.OR" and limit >= 6 else
        {pattern: 1 for pattern in TRUTH_PATTERNS}
        if capability == "B.XOR" and limit >= 4 else None
    )
    if quotas is None:
        shift = rotation % len(signatures)
        return tuple((signatures[shift:] + signatures[:shift])[:limit])
    scheduled = []
    for pattern in TRUTH_PATTERNS:
        group = [signature for signature in signatures if signature[1] == pattern]
        if not group:
            raise ValueError("FRAGILE_PRESERVATION_TRUTH_PATTERN_MISSING")
        count = min(quotas[pattern], len(group))
        shift = rotation % len(group)
        ordered = group[shift:] + group[:shift]
        scheduled.extend(ordered[:count])
    return tuple(scheduled[:limit])


def select_structural_preservation_rows(rows, fixed_rows, *, excluded_ids=frozenset(),
                                        rotation: int, limit: int) -> tuple[dict, ...]:
    """Select fresh rows matching rotating fixed structural signatures."""
    if type(rotation) is not int or rotation < 0 or type(limit) is not int or limit < 1:
        raise ValueError("FRAGILE_PRESERVATION_ROTATION_INVALID")
    desired = _signature_schedule(
        fixed_rows, rotation=rotation, limit=limit)
    excluded = set(excluded_ids)
    selected = {}
    for row in rows:
        if row.get("id") in excluded:
            continue
        signature = structural_signature(row)
        if signature in desired:
            selected.setdefault(signature, row)
    missing = [signature for signature in desired if signature not in selected]
    if missing:
        raise ValueError("FRAGILE_PRESERVATION_STRUCTURAL_SIGNATURE_MISSING")
    return tuple(selected[signature] for signature in desired)


def _pattern_gold(capability: str, pattern: tuple[bool, bool]) -> str:
    if capability == "B.OR":
        value = pattern[0] or pattern[1]
    elif capability == "B.XOR":
        value = pattern[0] != pattern[1]
    else:
        raise ValueError("FRAGILE_PRESERVATION_UNKNOWN_CAPABILITY")
    return "TRUE" if value else "FALSE"


def select_preservation_rows(rows, *, capabilities=CAPABILITIES,
                             excluded_ids=frozenset()) -> tuple[dict, ...]:
    """Pick fresh source siblings that cover each fragile truth-table cell once.

    Fixed examination identities are explicitly excluded. The rehearsal signal
    therefore teaches the same Boolean semantics without turning admission
    questions into lesson material.
    """
    requested = tuple(capabilities)
    if (not requested or len(requested) != len(set(requested)) or
            any(capability not in CAPABILITIES for capability in requested)):
        raise ValueError("FRAGILE_PRESERVATION_INVALID_CAPABILITY_SET")
    excluded = set(excluded_ids)
    selected = {}
    for row in rows:
        capability = row.get("capability")
        if capability not in requested or row.get("id") in excluded:
            continue
        raw = row.get("operand_truths")
        if (not isinstance(raw, (list, tuple)) or len(raw) != 2 or
                any(type(value) is not bool for value in raw)):
            raise ValueError("FRAGILE_PRESERVATION_OPERAND_PATTERN_INVALID")
        pattern = tuple(raw)
        if pattern not in TRUTH_PATTERNS or row.get("gold") != _pattern_gold(
                capability, pattern):
            raise ValueError("FRAGILE_PRESERVATION_SOURCE_GOLD_DRIFT")
        if not row.get("tokens"):
            raise ValueError("FRAGILE_PRESERVATION_SOURCE_TOKENS_MISSING")
        selected.setdefault((capability, pattern), row)
    required = {(capability, pattern)
                for capability in requested for pattern in TRUTH_PATTERNS}
    missing = required - set(selected)
    if missing:
        raise ValueError("FRAGILE_PRESERVATION_INCOMPLETE_TRUTH_TABLE")
    return tuple(selected[key] for key in sorted(selected)
                 if key in required)


def load_replay_rows(run_dir: Path, receipt: dict) -> tuple[dict, ...]:
    """Reuse the current materialized full-exam B cases, never generate new gold."""
    exam = receipt.get("last_exam") or {}
    scores = exam.get("scores") or {}
    if any(name not in scores for name in CAPABILITIES):
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
        raise ValueError("FRAGILE_REPLAY_COHORT_IDENTITY_DRIFT")
    cohort = make_cohort(stored["rows"], generator_version=stored["generator_version"],
                         seed=stored["seed"], rubric_version=stored["schema"])
    if cohort.digest != sha:
        raise ValueError("FRAGILE_REPLAY_COHORT_CONTENT_DRIFT")
    rows = tuple(row for row in cohort.rows if row["capability"] in CAPABILITIES)
    if len(rows) != 24 or len({row["id"] for row in rows}) != 24:
        raise ValueError("FRAGILE_REPLAY_INCOMPLETE_B_COHORT")
    for name in CAPABILITIES:
        group = [row for row in rows if row["capability"] == name]
        if (len(group) != 12 or
                scores[name].get("total") != 12 or
                sum(row["gold"] == "TRUE" for row in group) != 6 or
                sum(row["gold"] == "FALSE" for row in group) != 6):
            raise ValueError("FRAGILE_REPLAY_UNBALANCED_B_COHORT")
        for row in group:
            args = row["record"]["query"]["args"]
            pattern = [operand_truth(row["record"]["world"], arg) for arg in args]
            if (row.get("operand_truths") != pattern or
                    grade_b_gold(row["record"], name) != row["gold"] or
                    not row.get("tokens")):
                raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
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
