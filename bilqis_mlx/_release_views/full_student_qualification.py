"""Disposable actual-shape FP32+AdamW continuation comparison.

Loads the SHA-pinned original source strictly read-only. One synthetic CE step
is applied only to independent in-memory copies, never to a Bilqis run
checkpoint. Does NOT grant permission to run the student optimizer.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

from .backup import digest_file
from bilqis_mlx.runtime.mlx_parity import (clip_gradients, forward_arrays,
                         native_optimizer_to_mlx)
from .source import AUDITED_PARENT


def probe(checkpoint: Path, legacy_root: Path, *, tolerance=2e-3,
          verify_restart: bool = False, device: str = "cpu",
          grade_a_manifest: Path | None = None) -> dict:
    import mlx.core as mx
    import numpy as np
    import torch
    import torch.nn.functional as F
    from bilqis_development.continuation import load as native_load
    from bilqis_micro.graph import STATES

    checkpoint = checkpoint.resolve(strict=True)
    if digest_file(checkpoint) != AUDITED_PARENT.sha256:
        raise ValueError("FULL_CONTINUATION_PINNED_CHECKPOINT_CHANGED")
    if device not in ("cpu", "gpu"):
        raise ValueError("FULL_CONTINUATION_UNKNOWN_DEVICE")
    mx.set_default_device(mx.cpu if device == "cpu" else mx.gpu)
    torch.set_num_threads(1)
    source_model, source_optimizer, payload = native_load(checkpoint)
    if payload["config"]["precision"] != "fp32":
        raise ValueError("FULL_CONTINUATION_NOT_FP32")
    # These are detached, disposable working copies with no checkpoint path.
    cloned = copy.deepcopy(source_model)
    g = source_optimizer.param_groups[0]
    torch_optimizer = torch.optim.AdamW(cloned.parameters(), lr=g["lr"],
            betas=g["betas"], eps=g["eps"], weight_decay=g["weight_decay"],
            foreach=False)
    torch_optimizer.load_state_dict(source_optimizer.state_dict())
    ordered = [name for name,_ in cloned.named_parameters()]
    original_param_ids = {id(p):name for name,p in cloned.named_parameters()}
    ordered = [original_param_ids[id(p)] for p in torch_optimizer.param_groups[0]["params"]]
    native_weights = {name: weight.detach().clone()
                      for name, weight in cloned.state_dict().items()}
    copied, mlx_optimizer = native_optimizer_to_mlx(
        torch_optimizer.state_dict(), native_weights, parameter_order=ordered)
    parameters = {name: mx.array(weight.numpy(), dtype=mx.float32)
                  for name, weight in native_weights.items()}
    # Either synthetic tokens or realistic *candidate* Grade A source records,
    # never presented to a mutable real run.
    if grade_a_manifest is None:
        ids = np.array([[4, 6, 7, 8, 9], [9, 8, 7, 6, 4]], dtype=np.int32)
        lengths = np.array([5, 4], dtype=np.int32)
        answers = [STATES.index("TRUE"), STATES.index("FALSE")]
    else:
        from .grade_a_manifest import verify_manifest
        from .grade_a_probe import FAMILIES
        manifest = json.loads(Path(grade_a_manifest).read_text(encoding="utf-8"))
        verify_manifest(manifest, legacy_root, checkpoint)
        selected = [
            item for cap, _, _, _ in FAMILIES
            for item in (r for r in manifest["training_rows"]
                         if r["capability"] == cap)
            if item["gold"] in ("TRUE", "FALSE")
        ]
        selected = [next(r for r in selected if r["capability"] == cap
                         and r["gold"] == gold)
                    for cap, _, _, _ in FAMILIES for gold in ("TRUE", "FALSE")]
        lengths = np.array([len(r["tokens"]) for r in selected], dtype=np.int32)
        ids = np.zeros((len(selected), int(lengths.max())), dtype=np.int32)
        for i, item in enumerate(selected):
            ids[i,:len(item["tokens"])] = item["tokens"]
        answers = [STATES.index(item["gold"]) for item in selected]
    labels = torch.tensor(answers, dtype=torch.long)
    answer_ids = cloned.answer_ids.cpu().numpy().tolist()
    c = payload["config"]

    cloned.train()
    torch_optimizer.zero_grad(set_to_none=True)
    native_logits = cloned(torch.tensor(ids, dtype=torch.long),
                           torch.tensor(lengths, dtype=torch.long))
    native_loss = F.cross_entropy(native_logits, labels)
    native_loss.backward()
    def mlx_loss(weight_tree):
        logits = forward_arrays(mx, weight_tree, ids, lengths,
                                heads=c["heads"], layers=c["layers"],
                                answer_ids=answer_ids)
        one_hot = mx.array(np.eye(logits.shape[-1],dtype=np.float32)[answers])
        return mx.mean(mx.logsumexp(logits, axis=-1) -
                       mx.sum(logits * one_hot, axis=-1))
    mlx_value, mlx_grads = mx.value_and_grad(mlx_loss)(parameters)
    mx.eval(mlx_value, mlx_grads)
    if set(mlx_grads) != set(native_weights):
        raise ValueError("FULL_CONTINUATION_MISSING_MLX_GRADIENT")
    # The PyTorch source embedding freezes padding row 0. A raw MLX gather
    # has no padding_idx, so parity must compare the *effective masked* grad.
    embedding_gradient = mx.where(
        mx.arange(parameters["embedding.weight"].shape[0])[:,None] != 0,
        mlx_grads["embedding.weight"],
        mx.zeros_like(mlx_grads["embedding.weight"]))
    effective = {**mlx_grads, "embedding.weight": embedding_gradient}
    max_grad_error = max(float(np.max(np.abs(
        p.grad.detach().numpy() - np.asarray(effective[name]))))
        for name,p in cloned.named_parameters())
    initial_loss_error = abs(float(native_loss.item()) - float(mlx_value.item()))

    native_norm = torch.nn.utils.clip_grad_norm_(cloned.parameters(), 1.0)
    clipped, mlx_norm = clip_gradients(mx, effective, max_norm=1.0)
    # PyTorch's nn.Embedding(padding_idx=0) excludes row 0 from gradients.
    # Explicitly mask it before MLX optimizer update; all other rows agree.
    mask = mx.arange(parameters["embedding.weight"].shape[0])[:,None] != 0
    clipped["embedding.weight"] = mx.where(mask, clipped["embedding.weight"],
                                           mx.zeros_like(clipped["embedding.weight"]))
    mx.eval(clipped, mlx_norm)
    max_clipped_error = max(float(np.max(np.abs(
        p.grad.detach().numpy() - np.asarray(clipped[name]))))
        for name,p in cloned.named_parameters())
    torch_optimizer.step()
    mlx_optimizer.update(parameters, clipped)
    mx.eval(parameters, mlx_optimizer.state)
    max_weight_error = max(float(np.max(np.abs(
        cloned.state_dict()[name].detach().numpy() - np.asarray(parameters[name]))))
        for name in parameters)
    cloned_state = torch_optimizer.state_dict()
    maximum_moment_error = 0.0
    for pid,name in zip(cloned_state["param_groups"][0]["params"], ordered):
        cell = cloned_state["state"][pid]
        for native, field in (("exp_avg", "m"), ("exp_avg_sq", "v")):
            maximum_moment_error = max(maximum_moment_error,
                float(np.max(np.abs(cell[native].cpu().numpy() -
                                    np.asarray(mlx_optimizer.state[name][field])))))
    torch_step = int(next(iter(cloned_state["state"].values()))["step"].item())
    mlx_step = int(mlx_optimizer.state["step"].item())
    restart = None
    if verify_restart:
        from bilqis_mlx.runtime.mlx_checkpoint import (save_new_bundle,
                                     load_semantically_bound_bundle)
        # A throwaway bundle occupies only a private temporary directory;
        # the pinned source model/checkpoint and actual school runs are never
        # targets of the write, and no persistent champion is created.
        with tempfile.TemporaryDirectory(prefix="bilqis-disposable-parity-") as tmp:
            path = Path(tmp) / "scratch-full-student"
            receipt = save_new_bundle(
                path, parameters, mlx_optimizer,
                source_digest=AUDITED_PARENT.sha256,
                semantic_catalog=payload["graph"])
            fresh_params, fresh_opt, fresh_receipt, catalog = (
                load_semantically_bound_bundle(path))
            mx.eval(fresh_params, fresh_opt.state)
            restart_weights = max(
                float(np.max(np.abs(np.asarray(parameters[name]) -
                                    np.asarray(fresh_params[name]))))
                for name in parameters)
            restart_moments = max(
                float(np.max(np.abs(np.asarray(mlx_optimizer.state[name][field]) -
                                    np.asarray(fresh_opt.state[name][field]))))
                for name in parameters for field in ("m", "v"))
            if (receipt != fresh_receipt or
                    list(parameters) != list(fresh_params) or
                    int(fresh_opt.state["step"].item()) != mlx_step or
                    catalog["tokens"] != payload["graph"]["tokens"] or
                    restart_weights != 0.0 or restart_moments != 0.0):
                raise ValueError("FULL_CONTINUATION_DISPOSABLE_RESTART_DRIFT")
            restart = {
                "complete_39_tensor_weights_and_moments_reloaded": True,
                "weights_abs_delta": restart_weights,
                "moments_abs_delta": restart_moments,
                "optimizer_step": int(fresh_opt.state["step"].item()),
                "semantic_token_count": len(catalog["tokens"]),
                "temporary_bundle_size": receipt["uncompressed_parameter_and_moment_bytes"],
                "temporary_directory_cleaned_on_exit": True,
            }
    result = {
        "schema": "bilqis.mlx.disposable-full-continuation/v1",
        "source_sha256": AUDITED_PARENT.sha256,
        "source_graph_token_count": len(payload["graph"]["tokens"]),
        "candidate_grade_a_batch_used": grade_a_manifest is not None,
        "batch_size": int(len(ids)),
        "batch_max_sequence_length": int(ids.shape[1]),
        "tensor_count": len(ordered),
        "start_step": copied["native_step"],
        "mlx_device": device,
        "torch_step": torch_step,
        "mlx_step": mlx_step,
        "loss_delta": initial_loss_error,
        "gradient_max_abs_delta": max_grad_error,
        "gradient_clip_norm_delta": abs(float(native_norm.item()) -
                                         float(mlx_norm.item())),
        "clipped_gradient_max_abs_delta": max_clipped_error,
        "weight_max_abs_delta": max_weight_error,
        "moment_max_abs_delta": maximum_moment_error,
        "tolerance": tolerance,
        "source_file_unchanged": digest_file(checkpoint) == AUDITED_PARENT.sha256,
        "neural_updates_to_real_student": 0,
        "disposable_clone_steps": 1,
        "disposable_restart": restart,
        "human_training_authorized": False,
    }
    if (not result["source_file_unchanged"] or
            torch_step != copied["native_step"]+1 or
            mlx_step != torch_step or
            max(initial_loss_error,max_grad_error,max_clipped_error,
                max_weight_error,maximum_moment_error,
                result["gradient_clip_norm_delta"]) > tolerance):
        raise ValueError("FULL_CONTINUATION_PARITY_NOT_PROVEN:" +
                         json.dumps(result,sort_keys=True))
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--legacy-code-root",type=Path,required=True)
    p.add_argument("--checkpoint",type=Path,required=True)
    p.add_argument("--verify-disposable-restart", action="store_true")
    p.add_argument("--device",choices=("cpu","gpu"),default="cpu")
    p.add_argument("--grade-a-manifest",type=Path)
    args = p.parse_args(argv)
    root=args.legacy_code_root.resolve(strict=True)
    if not (root/"bilqis_development/continuation.py").is_file():
        p.error("Legacy source loader unavailable")
    sys.path.insert(0,str(root))
    sys.dont_write_bytecode=True
    print(json.dumps(probe(args.checkpoint,root,
                           verify_restart=args.verify_disposable_restart,
                           device=args.device,
                           grade_a_manifest=args.grade_a_manifest),
                     sort_keys=True,indent=2))


if __name__=="__main__":
    main()
