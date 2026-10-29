"""MLX inference, batches and single-student optimizer primitives."""
from __future__ import annotations

import bilqis_mlx.compatibility.live_releases as _compatibility_live_releases
import bilqis_mlx.learning.champion_confidence as _learning_champion_confidence
import bilqis_mlx.runtime.mlx_parity as _runtime_mlx_parity
import bilqis_mlx.semantics.foundation.abi as _semantics_abi
import pathlib as _pathlib


def _initial_model(source_checkpoint: _pathlib.Path):
    import mlx.core as mx
    from bilqis_development.continuation import load
    model, optimizer, payload = load(source_checkpoint)
    if (payload["config"]["precision"] != "fp32" or
            len(payload["graph"]["tokens"]) != _semantics_abi.HISTORICAL_PREFIX_SIZE):
        raise ValueError("HUMAN_TRAINER_HISTORICAL_SEMANTIC_ABI_INVALID")
    names = {id(p): name for name, p in model.named_parameters()}
    order = [names[id(p)] for p in optimizer.param_groups[0]["params"]]
    _, mlx_optimizer = _runtime_mlx_parity.native_optimizer_to_mlx(
        optimizer.state_dict(), model.state_dict(), parameter_order=order)
    parameters = {name: mx.array(weight.detach().numpy(), dtype=mx.float32)
                  for name, weight in model.state_dict().items()}
    mx.eval(parameters, mlx_optimizer.state)
    return parameters, mlx_optimizer, payload["config"], payload["graph"], (
        model.answer_ids.cpu().numpy().tolist())


def _make_batch(rows: list[dict], context: int = 96):
    import numpy as np
    if not rows:
        raise ValueError("HUMAN_TRAINER_EMPTY_BATCH")
    lengths = np.asarray([len(row["tokens"]) for row in rows], dtype=np.int32)
    if min(lengths) < 1 or max(lengths) > context:
        raise ValueError("HUMAN_TRAINER_SEQUENCE_OUTSIDE_LEGACY_CONTEXT")
    ids = np.zeros((len(rows), int(lengths.max())), dtype=np.int32)
    labels = np.zeros(len(rows), dtype=np.int32)
    for i, row in enumerate(rows):
        ids[i, :lengths[i]] = row["tokens"]
        labels[i] = {"FALSE": 0, "TRUE": 1}[row["gold"]]
    return ids, lengths, labels


def _predictions(mx, parameters, rows, config, answer_ids):
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        from bilqis_mlx.typed_answer_training import predict_rows
        return predict_rows(mx, parameters, rows, config["answer_heads"], config)
    import numpy as np
    result = {}
    batch_rows = _runtime_mlx_parity.inference_batch_rows(rows)
    for offset in range(0, len(rows), batch_rows):
        batch = rows[offset:offset+batch_rows]
        ids, lengths, _ = _make_batch(batch, parameters["position.weight"].shape[0])
        logits = _runtime_mlx_parity.forward_arrays(mx, parameters, ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        mx.eval(logits)
        binary = np.asarray(logits)[:, :2].argmax(axis=-1)
        result.update({row["id"]: ("TRUE" if int(value) else "FALSE")
                       for row, value in zip(batch, binary)})
    return result


def _train_score(mx, parameters, rows, config, answer_ids) -> float:
    result = _predictions(mx, parameters, rows, config, answer_ids)
    return sum(result[r["id"]] == r["gold"] for r in rows) / len(rows)


def _compatible_graphs(earlier, current):
    """A frozen earlier teacher retains its exact historical semantic prefix."""
    count = len(earlier["tokens"])
    return (earlier["tokens"] == current["tokens"][:count] and
            earlier["nodes"] == current["nodes"][:count] and
            all(current["row_contract_sha256"].get(s) == value
                for s, value in earlier["row_contract_sha256"].items()))


def _compatible_answer_config(config, graph):
    if "answer_heads" not in config:
        return config
    heads = config["answer_heads"]
    vocabulary = len(graph["tokens"])

    def readable(kind):
        ids = heads.get(kind, {}).get("token_ids", ())
        return bool(ids) and max(ids) < vocabulary

    if "numeric_active" in heads and readable("numeric_active"):
        maximum = len(heads["numeric_active"]["values"])-1
        compatible = _compatibility_live_releases.numeric_answer_heads(graph, maximum, prior_heads=heads)
    elif "boolean_operator" in heads and readable("boolean_operator"):
        compatible = _compatibility_live_releases.boolean_identification_answer_heads(graph)
    elif (heads.get("semantic_token", {}).get("values", ())[:vocabulary] == graph["tokens"] and
          heads["semantic_token"].get("token_ids") ==
          list(range(len(heads["semantic_token"]["values"])))):
        compatible = {kind: head for kind, head in heads.items()
                      if kind != "semantic_token" and readable(kind)}
        compatible["semantic_token"] = {
            **heads["semantic_token"], "values": list(graph["tokens"]),
            "token_ids": list(range(vocabulary))}
    else:
        raise ValueError("HUMAN_TRAINER_UNKNOWN_TYPED_ANSWER_CONFIG")
    return {**config, "answer_heads": compatible}


def _train_step(mx, parameters, optimizer, rows, config, answer_ids,
                *, champion_guidance=None):
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        from bilqis_mlx.typed_answer_training import typed_step
        return typed_step(mx, parameters, optimizer, rows, config["answer_heads"],
                          config, champion_guidance=champion_guidance)
    import numpy as np
    ids, lengths, labels = _make_batch(rows, parameters["position.weight"].shape[0])
    expected = mx.array(np.eye(2, dtype=np.float32)[labels])
    advice = None
    if champion_guidance is not None:
        target, weight = champion_guidance
        target = np.asarray(target, dtype=np.float32)
        weight = np.asarray(weight, dtype=np.float32)
        if (target.shape != (len(rows), 2) or weight.shape != (len(rows),) or
                not np.isfinite(target).all() or not np.isfinite(weight).all() or
                (weight < 0).any() or (weight > _learning_champion_confidence.MAX_INFLUENCE + 1e-6).any() or
                (target < 0).any() or
                not np.allclose(target.sum(axis=-1), 1., atol=1e-6)):
            raise ValueError("CHAMPION_CONFIDENCE_TRAINING_GUIDANCE_INVALID")
        advice = (mx.array(target), mx.array(weight))

    def objective(weights):
        logits = _runtime_mlx_parity.forward_arrays(mx, weights, ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        typed = logits[:, :2]
        normalizer = mx.logsumexp(typed, axis=-1)
        loss = mx.mean(normalizer - mx.sum(typed * expected, axis=-1))
        if advice is not None:
            # Frozen confidence teaches only through this bounded gradient;
            # no exam inference ever reads the champion-adjusted logits.
            soft_target, strength = advice
            loss = loss + mx.mean(strength *
                 (normalizer - mx.sum(typed * soft_target, axis=-1)))
        return loss

    loss, gradients = mx.value_and_grad(objective)(parameters)
    # Native torch.nn.Embedding(padding_idx=0) never trains padding row.
    pad_mask = mx.arange(parameters["embedding.weight"].shape[0])[:, None] != 0
    gradients["embedding.weight"] = mx.where(
        pad_mask, gradients["embedding.weight"],
        mx.zeros_like(gradients["embedding.weight"]))
    clipped, norm = _runtime_mlx_parity.clip_gradients(mx, gradients, max_norm=1.0)
    optimizer.update(parameters, clipped)
    mx.eval(parameters, optimizer.state, loss, norm)
    return float(loss.item()), float(norm.item())
