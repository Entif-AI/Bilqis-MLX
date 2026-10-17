"""Small, source-gated confidence advice from frozen whole-student champions.

Votes affect the causal student's supervised gradient, not independent exams,
oracle golds, optimizer lineage, or student checkpoint selection. Unique
checkpoints vote once; their weight scales with proven simultaneous mastery.
"""
from __future__ import annotations

import numpy as np


POLICY = "bilqis.mlx.champion-confidence/v1"
MAX_INFLUENCE = 0.08
TEMPERATURE = 1.5


def champion_roster(frontier: dict, grade: str) -> tuple[dict, ...]:
    """Only current-grade perfect role owners advise that grade's lessons."""
    unique = {}
    for item in frontier.values():
        if not item["capability"].startswith(grade + "."):
            continue
        breadth = item.get("breadth")
        mastered = item.get("perfect_capabilities")
        if (type(breadth) is not int or breadth < 1 or
                not isinstance(mastered, list) or len(mastered) != breadth or
                item["capability"] not in mastered or
                not item["checkpoint"].get("model_and_native_adamw")):
            raise ValueError("CHAMPION_CONFIDENCE_RANK_NOT_VERIFIED")
        sha = item["checkpoint"]["sha256"]
        if sha not in unique or breadth > unique[sha]["breadth"]:
            unique[sha] = {"checkpoint": item["checkpoint"], "breadth": breadth}
    return tuple(unique[sha] for sha in sorted(unique))


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
