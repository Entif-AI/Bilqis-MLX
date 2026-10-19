"""Typed MLX output-caste adapter for a separately admitted future curriculum.

No source or student is loaded here. The existing two-class Grade A trainer
is deliberately untouched. A native full-catalog output target accompanies
each oracle-attested direct numeral, alongside a restricted numeric exercise
and the original five-way evidence head. All three reuse the same tied
embedding weights, rather than creating a new classifier or semantic catalog.
All model steps must remain operator-controlled; tests use disposable arrays.
"""
from __future__ import annotations

import numpy as np

from bilqis_mlx.runtime.mlx_parity import clip_gradients, forward_arrays


TRAIN_CASTES = ("numeric_0_3", "numeric_active", "numeric_full_101",
                "binary", "evidence", "semantic_token")


def prepare_typed_batches(rows: list[dict], heads: dict) -> dict:
    """Teach direct numerals both as numeric exercises and real output tokens."""
    if not rows:
        raise ValueError("ANSWER_CASTE_EMPTY_LESSON")
    native = heads.get("semantic_token") or {}
    vocabulary = native.get("values") or []
    if (not vocabulary or len(vocabulary) != len(set(vocabulary)) or
            native.get("token_ids") != list(range(len(vocabulary)))):
        raise ValueError("ANSWER_CASTE_FULL_VOCABULARY_ABI_INVALID")
    grouped = {}
    for row in rows:
        kind = row.get("answer_kind")
        if kind not in TRAIN_CASTES:
            raise ValueError("ANSWER_CASTE_NOT_ADMITTED_FOR_TRAINING")
        head = heads.get(kind) or {}
        labels = head.get("values") or []
        answer_ids = head.get("token_ids") or []
        sizes = {"numeric_0_3":4, "numeric_full_101":101, "evidence":5, "binary":2}
        if (len(labels) != len(answer_ids) or
                len(set(labels)) != len(labels) or
                any(type(i) is not int or not 0 <= i < len(vocabulary) for i in answer_ids) or
                kind in sizes and len(labels) != sizes[kind] or
                kind == "numeric_active" and (len(labels) < 2 or
                         labels != [str(i) for i in range(len(labels))]) or
                kind == "semantic_token" and len(labels) != len(vocabulary) or
                len(set(answer_ids)) != len(answer_ids) or
                kind == "numeric_0_3" and labels != ["0", "1", "2", "3"] or
                kind == "numeric_full_101" and labels != [str(i) for i in range(101)] or
                kind in ("evidence", "binary") and labels[:2] != ["FALSE", "TRUE"]):
            raise ValueError("ANSWER_CASTE_UNTRUSTED_HEAD_ABI")
        if row.get("gold") not in labels:
            raise ValueError("ANSWER_CASTE_GOLD_OUTSIDE_HEAD")
        tokens = row.get("tokens")
        if (not isinstance(tokens, list) or not 1 <= len(tokens) <= 96 or
                any(type(t) is not int or t < 0 for t in tokens)):
            raise ValueError("ANSWER_CASTE_INPUT_TOKENS_INVALID")
        grouped.setdefault(kind, []).append(row)
        if kind.startswith("numeric_") or kind == "semantic_token":
            # A restricted numeric readout by itself does not teach selection from
            # Bilqis's entire semantic catalog. The additional supervised
            # response competes against every admitted output token. An
            # explicit semantic-token row may name another existing identity,
            # but must still be source-qualified before any curriculum release.
            identity = ("school.number." + row["gold"]
                        if kind.startswith("numeric_") else row["gold"])
            binding = row.get("native_output")
            if (identity not in vocabulary or
                    binding != {"identity": identity,
                                "token_id": vocabulary.index(identity)} or
                    kind.startswith("numeric_") and
                    head["token_ids"][labels.index(row["gold"])] != binding["token_id"]):
                raise ValueError("ANSWER_CASTE_NATIVE_SEMANTIC_TARGET_MISMATCH")
            if kind != "semantic_token":
                grouped.setdefault("semantic_token", []).append({
                    **row, "answer_kind": "semantic_token", "gold": identity})
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


def predict_rows(mx, weights, rows, heads, config) -> dict[str, str]:
    """Inference reads tokens and declared answer mode, never specimen gold."""
    result = {}
    for offset in range(0, len(rows), 24):
        group = rows[offset:offset+24]
        for kind in {row["answer_kind"] for row in group}:
            if kind not in TRAIN_CASTES:
                raise ValueError("ANSWER_CASTE_NOT_ADMITTED_FOR_INFERENCE")
            own = [row for row in group if row["answer_kind"] == kind]
            head = heads["semantic_token" if kind.startswith("numeric_") else kind]
            vocabulary = heads["semantic_token"]["values"]
            if len(vocabulary) != weights["embedding.weight"].shape[0]:
                raise ValueError("ANSWER_CASTE_MODEL_FULL_VOCABULARY_DRIFT")
            lengths = np.asarray([len(row["tokens"]) for row in own], dtype=np.int32)
            if any(not 1 <= n <= 96 for n in lengths) or any(
                    type(t) is not int or not 0 <= t < len(vocabulary)
                    for row in own for t in row["tokens"]):
                raise ValueError("ANSWER_CASTE_INPUT_TOKENS_INVALID")
            ids = np.zeros((len(own), int(lengths.max())), dtype=np.int32)
            for i, row in enumerate(own):
                ids[i, :lengths[i]] = row["tokens"]
            logits = forward_arrays(mx, weights, ids, lengths,
                heads=config["heads"], layers=config["layers"], answer_ids=head["token_ids"])
            mx.eval(logits)
            for row, index in zip(own, np.asarray(logits).argmax(-1).tolist()):
                label = head["values"][index]
                result[row["id"]] = (label.removeprefix("school.number.")
                    if kind.startswith("numeric_") and label.startswith("school.number.")
                    else "TOKEN:" + label if kind.startswith("numeric_") else label)
    return result


def _check_model_shape(weights, batches):
    emb = weights["embedding.weight"]
    positions = weights["position.weight"].shape[0]
    if ("semantic_token" in batches and
            len(batches["semantic_token"]["answer_ids"]) != emb.shape[0]):
        raise ValueError("ANSWER_CASTE_MODEL_FULL_VOCABULARY_DRIFT")
    for batch in batches.values():
        if (max(batch["answer_ids"]) >= emb.shape[0] or
                int(batch["ids"].max()) >= emb.shape[0] or
                int(batch["lengths"].max()) > positions):
            raise ValueError("ANSWER_CASTE_MODEL_VOCAB_OR_CONTEXT_MISMATCH")


def _objective(mx, weights, batches, config, *, champion_guidance=None):
    losses = []
    champion_guidance = champion_guidance or {}
    if set(champion_guidance) - set(batches):
        raise ValueError("TYPED_CONFIDENCE_UNKNOWN_HEAD")
    for kind, batch in batches.items():
        logits = forward_arrays(
            mx, weights, batch["ids"], batch["lengths"],
            heads=config["heads"], layers=config["layers"],
            answer_ids=batch["answer_ids"])
        target_index = mx.array(np.asarray(batch["target_indices"],
                                           dtype=np.int32))[:, None]
        correct_logit = mx.take_along_axis(logits,target_index,axis=-1)[:,0]
        normalizer = mx.logsumexp(logits, axis=-1)
        loss = mx.mean(normalizer - correct_logit)
        if kind in champion_guidance:
            target, strength = champion_guidance[kind]
            target = np.asarray(target, dtype=np.float32)
            strength = np.asarray(strength, dtype=np.float32)
            if (target.shape != (len(batch["target_indices"]), len(batch["answer_ids"])) or
                    strength.shape != (len(batch["target_indices"]),) or
                    not np.isfinite(target).all() or not np.isfinite(strength).all() or
                    (target < 0).any() or (strength < 0).any() or
                    (strength > .08 + 1e-6).any() or
                    not np.allclose(target.sum(axis=-1), 1., atol=1e-5)):
                raise ValueError("TYPED_CONFIDENCE_INVALID_SOFT_TARGET")
            loss = loss + mx.mean(mx.array(strength) *
                (normalizer - mx.sum(logits * mx.array(target), axis=-1)))
        losses.append(loss)
    # High-fidelity direct numeric supervision is not drowned out by the
    # two assertion/contrast examples accompanying every one direct answer.
    return sum(losses) / len(losses)


def typed_objective(mx, weights, rows, heads, config, *, champion_guidance=None):
    batches = prepare_typed_batches(rows, heads)
    _check_model_shape(weights, batches)
    return _objective(mx, weights, batches, config,
                      champion_guidance=champion_guidance)


def typed_step(mx, weights, optimizer, rows, heads, config, *,
               champion_guidance=None):
    """Operator adapter, exercised only against synthetic models in tests."""
    batches = prepare_typed_batches(rows, heads)
    _check_model_shape(weights, batches)
    loss, gradients = mx.value_and_grad(
        lambda current: _objective(mx, current, batches, config,
                                   champion_guidance=champion_guidance))(weights)
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
