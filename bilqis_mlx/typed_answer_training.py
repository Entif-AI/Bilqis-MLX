"""Typed MLX output-caste adapter for a separately admitted future curriculum.

No source or student is loaded here. The existing two-class Grade A trainer
is deliberately untouched. A four-way numeric head and five-way evidence
head reuse the model's *original tied embedding*, as School50 v10 did.
All model steps must remain operator-controlled; tests use disposable arrays.
"""
from __future__ import annotations

import numpy as np

from .mlx_parity import clip_gradients, forward_arrays


TRAIN_CASTES = ("numeric_0_3", "evidence")


def prepare_typed_batches(rows: list[dict], heads: dict) -> dict:
    """Partition mixed supervision by output type, never merge softmaxes."""
    if not rows:
        raise ValueError("ANSWER_CASTE_EMPTY_LESSON")
    grouped = {}
    for row in rows:
        kind = row.get("answer_kind")
        if kind not in TRAIN_CASTES:
            raise ValueError("ANSWER_CASTE_NOT_ADMITTED_FOR_TRAINING")
        head = heads.get(kind) or {}
        labels = head.get("values") or []
        answer_ids = head.get("token_ids") or []
        if (len(labels) != len(answer_ids) or len(labels) not in (4, 5) or
                len(set(answer_ids)) != len(answer_ids) or
                kind == "numeric_0_3" and labels != ["0", "1", "2", "3"] or
                kind == "evidence" and labels[:2] != ["FALSE", "TRUE"]):
            raise ValueError("ANSWER_CASTE_UNTRUSTED_HEAD_ABI")
        if row.get("gold") not in labels:
            raise ValueError("ANSWER_CASTE_GOLD_OUTSIDE_HEAD")
        tokens = row.get("tokens")
        if (not isinstance(tokens, list) or not 1 <= len(tokens) <= 96 or
                any(type(t) is not int or t < 0 for t in tokens)):
            raise ValueError("ANSWER_CASTE_INPUT_TOKENS_INVALID")
        grouped.setdefault(kind, []).append(row)
    result = {}
    for kind, group in grouped.items():
        head = heads[kind]
        width = max(len(row["tokens"]) for row in group)
        ids = np.zeros((len(group), width), dtype=np.int32)
        lengths = np.empty(len(group), dtype=np.int32)
        indices = []
        for i, row in enumerate(group):
            n = len(row["tokens"])
            ids[i, :n] = row["tokens"]
            lengths[i] = n
            indices.append(head["values"].index(row["gold"]))
        result[kind] = {"ids": ids, "lengths": lengths,
                        "target_indices": indices,
                        "gold_labels": [row["gold"] for row in group],
                        "answer_ids": list(head["token_ids"]),
                        "row_ids": [row.get("id") for row in group]}
    return result


def _check_model_shape(weights, batches):
    emb = weights["embedding.weight"]
    positions = weights["position.weight"].shape[0]
    for batch in batches.values():
        if (max(batch["answer_ids"]) >= emb.shape[0] or
                int(batch["ids"].max()) >= emb.shape[0] or
                int(batch["lengths"].max()) > positions):
            raise ValueError("ANSWER_CASTE_MODEL_VOCAB_OR_CONTEXT_MISMATCH")


def _objective(mx, weights, batches, config):
    losses = []
    for batch in batches.values():
        logits = forward_arrays(
            mx, weights, batch["ids"], batch["lengths"],
            heads=config["heads"], layers=config["layers"],
            answer_ids=batch["answer_ids"])
        targets = mx.array(np.eye(len(batch["answer_ids"]), dtype=np.float32)
                           [batch["target_indices"]])
        losses.append(mx.mean(mx.logsumexp(logits, axis=-1) -
                              mx.sum(logits * targets, axis=-1)))
    # High-fidelity direct numeric supervision is not drowned out by the
    # two assertion/contrast examples accompanying every one direct answer.
    return sum(losses) / len(losses)


def typed_objective(mx, weights, rows, heads, config):
    batches = prepare_typed_batches(rows, heads)
    _check_model_shape(weights, batches)
    return _objective(mx, weights, batches, config)


def typed_step(mx, weights, optimizer, rows, heads, config):
    """Operator adapter, exercised only against synthetic models in tests."""
    batches = prepare_typed_batches(rows, heads)
    _check_model_shape(weights, batches)
    loss, gradients = mx.value_and_grad(
        lambda current: _objective(mx, current, batches, config))(weights)
    pad_mask = mx.arange(weights["embedding.weight"].shape[0])[:, None] != 0
    gradients["embedding.weight"] = mx.where(
        pad_mask, gradients["embedding.weight"],
        mx.zeros_like(gradients["embedding.weight"]))
    clipped, norm = clip_gradients(mx, gradients, max_norm=1.0)
    optimizer.update(weights, clipped)
    mx.eval(weights, optimizer.state, loss, norm)
    return float(loss.item()), float(norm.item())


def evaluate_rows(mx, weights, rows, heads, config, *,
                  numeric_scope="numeric_0_3") -> dict:
    """Observe restricted-4 and unrestricted-101 separately, never conflate."""
    if numeric_scope not in ("numeric_0_3", "numeric_full_101"):
        raise ValueError("ANSWER_CASTE_UNKNOWN_NUMERIC_DIAGNOSTIC")
    batches = prepare_typed_batches(rows, heads)
    if numeric_scope == "numeric_full_101" and "numeric_0_3" in batches:
        renamed = batches.pop("numeric_0_3")
        head = heads["numeric_full_101"]
        if (len(head["token_ids"]) != 101 or
                head["token_ids"][:4] != heads["numeric_0_3"]["token_ids"]):
            raise ValueError("ANSWER_CASTE_FULL_101_ABI_DRIFT")
        renamed["answer_ids"] = list(head["token_ids"])
        batches["numeric_full_101"] = renamed
    _check_model_shape(weights, batches)
    report = {}
    for kind, batch in batches.items():
        logits = forward_arrays(
            mx, weights, batch["ids"], batch["lengths"],
            heads=config["heads"], layers=config["layers"],
            answer_ids=batch["answer_ids"])
        mx.eval(logits)
        predicted = np.asarray(logits).argmax(-1).tolist()
        report[kind] = {
            "answer_classes": len(batch["answer_ids"]),
            "correct": sum(i == j for i, j in zip(predicted, batch["target_indices"])),
            "total": len(predicted),
            "scope": "SOURCE_TRAINING_OR_PREQUALIFIED_DEVELOPMENT_ONLY",
            "row_ids": batch["row_ids"],
        }
    return report
