"""Deterministic lesson-batch selection and missed-lesson replay."""
from __future__ import annotations

import random as _random

def choose_lesson_batch(rows: list[dict], policy: dict,
                        seed: int, *, batch_size=32) -> list[dict]:
    """Balance both truth values; policy shapes selection, never gold answers."""
    if not rows or batch_size < 2 or batch_size % 2:
        raise ValueError("HUMAN_TRAINER_INVALID_LESSON_BATCH_SIZE")
    rng = _random.Random(seed)
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        # Sample linked direct/TRUE/FALSE views from the same verified meaning.
        # This is an answer contract, independent of old/new lesson allocation.
        sources = {}
        for row in rows:
            sources.setdefault(row["source_id"], []).append(row)
        chosen = []
        groups = list(sources.values())
        while len(chosen) < batch_size:
            chosen.extend(rng.choice(groups))
        chosen = chosen[:batch_size]
        rng.shuffle(chosen)
        return chosen
    truths = {label: [r for r in rows if r["gold"] == label]
              for label in ("FALSE", "TRUE")}
    if any(not values for values in truths.values()):
        raise ValueError("HUMAN_TRAINER_MISSING_BINARY_TRAINING_CLASS")
    if policy["depth"] >= 3:
        # No invented composite concepts: emphasize long *attested* records.
        for value in truths.values():
            value.sort(key=lambda r: (-len(r["tokens"]), r["id"]))
    if policy["contrast"] >= 0.5:
        chosen = [rng.choice(truths[label]) for _ in range(batch_size // 2)
                  for label in ("TRUE", "FALSE")]
    else:
        chosen = [rng.choice(rows) for _ in range(batch_size)]
    rng.shuffle(chosen)
    return chosen


def replay_missed_lessons(chosen: list[dict], missed: list[dict], *,
                          reserved_ids=()) -> list[dict]:
    """Guarantee every requested missed construction reaches this optimizer batch."""
    if len(missed) > len(chosen):
        raise ValueError("HUMAN_TRAINER_MISS_REPLAY_EXCEEDS_BATCH")
    result = list(chosen)
    reserved = set(reserved_ids)
    consumed = {index for index, row in enumerate(result)
                if row.get("id") in reserved}
    for item in missed:
        replacement = next((i for i, row in enumerate(result)
                            if i not in consumed and row["gold"] == item["gold"]), None)
        if replacement is None:
            raise ValueError("HUMAN_TRAINER_MISS_REPLAY_ANSWER_CLASS_CAPACITY")
        result[replacement] = item
        consumed.add(replacement)
    return result
