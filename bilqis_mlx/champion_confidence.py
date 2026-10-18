"""Small, source-gated confidence advice from frozen whole-student champions.

Votes affect the causal student's supervised gradient, not independent exams,
oracle golds, optimizer lineage, or student checkpoint selection. Live adviser
inference is deduplicated by checkpoint, but each active maxed capability role
contributes one direct vote; a shared checkpoint is counted once per role.
"""
from __future__ import annotations

import numpy as np


POLICY = "bilqis.mlx.champion-confidence/v1"
MAX_INFLUENCE = 0.08
TEMPERATURE = 1.5


def champion_roster(frontier: dict, grade: str, *, snapshot=None) -> tuple[dict, ...]:
    """One direct mentor per checkpoint with positive proven perfect breadth.

    A frozen grade soup snapshot identifies the *current* champion roles.
    Historical examinations remain in the frontier for provenance, but an
    earlier-rubric role is not another independently entitled mentor vote.
    Best-score roles below perfection remain valid championship/soup evidence,
    but contribute zero direct perfect-breadth mentor influence.
    The optional unscoped form is retained for source-only legacy fixtures.
    """
    if snapshot is not None:
        roles = snapshot.get("roles")
        if (snapshot.get("grade") != grade or not isinstance(roles, list) or
                len(roles) != snapshot.get("vote_count") or
                len({r.get("capability") for r in roles}) != len(roles) or
                any(not r.get("capability", "").startswith(grade + ".")
                    for r in roles)):
            raise ValueError("CHAMPION_CONFIDENCE_ACTIVE_GRADE_ROLE_DRIFT")
        selected = []
        for role in roles:
            key = role["rubric"] + ":" + role["capability"]
            item = frontier.get(key)
            if (item is None or item["capability"] != role["capability"] or
                    item["checkpoint"]["sha256"] != role["checkpoint_sha256"]):
                raise ValueError("CHAMPION_CONFIDENCE_ACTIVE_ROLE_PROVENANCE_DRIFT")
            selected.append(item)
    else:
        selected = frontier.values()
    unique = {}
    for item in selected:
        if not item["capability"].startswith(grade + "."):
            continue
        breadth = item.get("breadth")
        mastered = item.get("perfect_capabilities")
        if (type(breadth) is not int or breadth < 0 or
                not isinstance(mastered, list) or len(mastered) != breadth or
                not item["checkpoint"].get("model_and_native_adamw")):
            raise ValueError("CHAMPION_CONFIDENCE_RANK_NOT_VERIFIED")
        # Best-score championship is broader than perfect-witness status.
        # A subperfect role stays valid for title/soup accounting but must not
        # itself recruit direct perfect-breadth advice. If this same checkpoint
        # owns another perfect role in the grade, that role will recruit it once.
        if breadth == 0 or item["capability"] not in mastered:
            continue
        sha = item["checkpoint"]["sha256"]
        if sha not in unique or breadth > unique[sha]["breadth"]:
            unique[sha] = {"checkpoint": item["checkpoint"], "breadth": breadth}
    return tuple(unique[sha] for sha in sorted(unique))


def perfect_role_roster(frontier: dict, grade_soups: dict) -> tuple[dict, ...]:
    """One direct vote per active maxed capability role, across all grades.

    Several capability roles may share one intact checkpoint. Inference may be
    deduplicated by checkpoint, but voting weight remains the number of active
    perfect roles that checkpoint owns, not its historical/global breadth.
    """
    if not isinstance(frontier, dict) or not isinstance(grade_soups, dict):
        raise ValueError("CHAMPION_CONFIDENCE_ROLE_ROSTER_INVALID")
    unique = {}
    for grade, snapshot in sorted(grade_soups.items()):
        if not isinstance(snapshot, dict):
            raise ValueError("CHAMPION_CONFIDENCE_ACTIVE_GRADE_ROLE_DRIFT")
        roles = snapshot.get("roles")
        if (snapshot.get("grade") != grade or not isinstance(roles, list) or
                len(roles) != snapshot.get("vote_count") or
                len({role.get("capability") for role in roles}) != len(roles) or
                any(not role.get("capability", "").startswith(grade + ".")
                    for role in roles)):
            raise ValueError("CHAMPION_CONFIDENCE_ACTIVE_GRADE_ROLE_DRIFT")
        for role in roles:
            capability = role["capability"]
            key = role["rubric"] + ":" + capability
            item = frontier.get(key)
            if (item is None or item.get("capability") != capability or
                    item.get("checkpoint", {}).get("sha256") != role.get(
                        "checkpoint_sha256")):
                raise ValueError("CHAMPION_CONFIDENCE_ACTIVE_ROLE_PROVENANCE_DRIFT")
            correct, total = role.get("correct"), role.get("total")
            if (type(correct) is not int or type(total) is not int or total < 1 or
                    not 0 <= correct <= total):
                raise ValueError("CHAMPION_CONFIDENCE_ACTIVE_ROLE_SCORE_DRIFT")
            if correct != total:
                continue
            mastered = item.get("perfect_capabilities")
            if (not isinstance(mastered, list) or capability not in mastered or
                    item.get("correct") != item.get("total") or
                    not item.get("checkpoint", {}).get("model_and_native_adamw")):
                raise ValueError("CHAMPION_CONFIDENCE_PERFECT_ROLE_DRIFT")
            pointer = item["checkpoint"]
            sha = pointer["sha256"]
            mentor = unique.setdefault(sha, {
                "checkpoint": pointer,
                "breadth": 0,
                "source_grade_votes": {},
                "capabilities": [],
            })
            mentor["breadth"] += 1
            mentor["source_grade_votes"][grade] = (
                mentor["source_grade_votes"].get(grade, 0) + 1)
            mentor["capabilities"].append(capability)
    return tuple({**unique[sha],
                  "source_grade_votes": dict(sorted(
                      unique[sha]["source_grade_votes"].items())),
                  "capabilities": tuple(sorted(unique[sha]["capabilities"]))}
                 for sha in sorted(unique))


def vote_targets(votes, labels, *, eligible_capabilities: int,
                 teacher_distill: float):
    """Return soft targets and bounded per-row weights for gold-agreeing votes.

    Each champion contributes MAX_INFLUENCE * teacher_distill * breadth/N,
    at most MAX_INFLUENCE in total for any row. Wrong votes are ignored.
    Teacher-selected distillation strength remains authoritative.
    """
    return vote_targets_typed(votes, labels, classes=2,
                              eligible_capabilities=eligible_capabilities,
                              teacher_distill=teacher_distill)


def vote_targets_typed(votes, labels, *, classes: int,
                       eligible_capabilities: int, teacher_distill: float):
    """The same source-gold-agreeing bounded confidence for any admitted head.

    Dense one-hot class targets are never allocated. A wrong mentor simply
    contributes no advice; independent scorer logits remain untouched.
    """
    labels = np.asarray(labels, dtype=np.int64)
    if (type(classes) is not int or classes < 2 or
            labels.ndim != 1 or (labels < 0).any() or
            (labels >= classes).any() or
            type(eligible_capabilities) is not int or eligible_capabilities < 1 or
            not np.isfinite(teacher_distill) or not 0 <= teacher_distill <= 1):
        raise ValueError("CHAMPION_CONFIDENCE_INVALID_INPUT")
    target = np.zeros((len(labels), classes), dtype=np.float64)
    weight = np.zeros(len(labels), dtype=np.float64)
    for breadth, raw in votes:
        raw = np.asarray(raw, dtype=np.float64)
        if (type(breadth) not in (int, float) or
                not np.isfinite(breadth) or not 0 < breadth <= eligible_capabilities or
                raw.shape != (len(labels), classes) or not np.isfinite(raw).all()):
            raise ValueError("CHAMPION_CONFIDENCE_INVALID_VOTE")
        accepted = np.argmax(raw, axis=-1) == labels
        if not accepted.any():
            continue
        scaled = raw / TEMPERATURE
        scaled -= scaled.max(axis=-1, keepdims=True)
        probabilities = np.exp(scaled)
        probabilities /= probabilities.sum(axis=-1, keepdims=True)
        contribution = MAX_INFLUENCE * teacher_distill * breadth / eligible_capabilities
        target[accepted] += contribution * probabilities[accepted]
        weight[accepted] += contribution
    active = weight > 0
    target[active] /= weight[active, None]
    target[~active] = 1.0 / classes
    weight = np.minimum(weight, MAX_INFLUENCE)
    return target.astype(np.float32), weight.astype(np.float32)
