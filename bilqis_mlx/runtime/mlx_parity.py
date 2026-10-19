"""Read-only whole-student PyTorch/MLX FP32 parity and AdamW-state mapping.

No saved checkpoint is written; no gradients or optimizer updates are run on the
historical student. A positive forward-and-moment result is still not proof of
MLX *training continuation* parity. That requires a separately authorized,
fully disposable clone with controlled update comparisons.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from bilqis_mlx.backup import digest_file
from bilqis_mlx.source import AUDITED_PARENT


def _norm(mx, values, gamma):
    mean = mx.mean(values, axis=-1, keepdims=True)
    delta = values - mean
    var = mx.mean(delta * delta, axis=-1, keepdims=True)
    return delta * mx.rsqrt(var + 1e-5) * gamma


def forward_arrays(mx, tensors, ids, lengths, *, heads: int, layers: int, answer_ids):
    """Differentiable FP32 MLX forward; never silently detach gradients."""
    import numpy as np
    ids = np.asarray(ids, dtype=np.int32)
    lengths = np.asarray(lengths, dtype=np.int32)
    if (ids.ndim != 2 or lengths.shape != (len(ids),) or
            any(length < 1 or length > ids.shape[1] for length in lengths)):
        raise ValueError("MLX_INVALID_INPUT_LENGTHS")
    batch, sequence = ids.shape
    dimension = tensors["embedding.weight"].shape[1]
    if dimension % heads:
        raise ValueError("MLX_ATTENTION_HEAD_GEOMETRY_DRIFT")
    x = tensors["embedding.weight"][mx.array(ids)] + tensors["position.weight"][mx.arange(sequence)][None]
    for layer in range(layers):
        pre = f"blocks.{layer}."
        z = _norm(mx, x, tensors[pre+"n1.weight"])
        qkv = z @ mx.transpose(tensors[pre+"qkv.weight"])
        parts = [qkv[:,:,i*dimension:(i+1)*dimension] for i in range(3)]
        q,k,v = [mx.transpose(mx.reshape(p,(batch,sequence,heads,dimension//heads)),(0,2,1,3))
                 for p in parts]
        scores = (q @ mx.transpose(k,(0,1,3,2))) / math.sqrt(dimension//heads)
        causal = mx.triu(mx.ones((sequence,sequence),dtype=mx.bool_), k=1)
        scores = mx.where(causal[None,None],-1e9,scores)
        attention = mx.softmax(scores, axis=-1) @ v
        attention = mx.reshape(mx.transpose(attention,(0,2,1,3)),(batch,sequence,dimension))
        x = x + attention @ mx.transpose(tensors[pre+"proj.weight"])
        z = _norm(mx, x, tensors[pre+"n2.weight"])
        z = mx.maximum(z @ mx.transpose(tensors[pre+"up.weight"]),0.0)
        x = x + (z*z) @ mx.transpose(tensors[pre+"down.weight"])
    x = _norm(mx, x, tensors["norm.weight"])
    hidden = mx.stack([x[i,int(lengths[i])-1] for i in range(batch)])
    logits = hidden @ mx.transpose(tensors["embedding.weight"][mx.array(answer_ids,dtype=mx.int32)])
    return logits


def forward(mx, tensors, ids, lengths, *, heads: int, layers: int, answer_ids):
    """Read-only NumPy projection of the same differentiable MLX forward."""
    import numpy as np
    logits = forward_arrays(mx, tensors, ids, lengths, heads=heads,
                            layers=layers, answer_ids=answer_ids)
    mx.eval(logits)
    return np.asarray(logits)


def clip_gradients(mx, gradients, *, max_norm: float):
    """Global L2 clipping matching PyTorch's native max-norm boundary."""
    from mlx.utils import tree_flatten, tree_map
    import math
    if not math.isfinite(max_norm) or max_norm <= 0:
        raise ValueError("MLX_INVALID_GRADIENT_CLIP_NORM")
    leaves = [array for _,array in tree_flatten(gradients)]
    if not leaves:
        raise ValueError("MLX_EMPTY_GRADIENT_TREE")
    norms = mx.stack([mx.sum(array * array) for array in leaves])
    total = mx.sqrt(mx.sum(norms))
    factor = mx.minimum(mx.array(1.0, dtype=total.dtype),
                        max_norm / (total + 1e-6))
    return tree_map(lambda array: array * factor, gradients), total


def native_optimizer_to_mlx(optimizer_state, model_weights, *, parameter_order):
    """Copy moments under exact original parameter IDs; no optimizer step."""
    import numpy as np
    import mlx.core as mx
    import mlx.optimizers as optim
    groups = optimizer_state["param_groups"]
    if len(groups) != 1:
        raise ValueError("MLX_EXPECT_ONE_NATIVE_ADAMW_GROUP")
    config = groups[0]
    if config.get("amsgrad") or config.get("maximize"):
        raise ValueError("MLX_UNSUPPORTED_ADAMW_VARIANT")
    param_ids = config["params"]
    keys = list(parameter_order)
    if (len(param_ids) != len(keys) or len(keys) != len(set(keys)) or
            set(keys) != set(model_weights) or
            set(optimizer_state["state"]) != set(param_ids)):
        raise ValueError("MLX_PARAM_ID_MAPPING_NOT_BIJECTIVE")
    mlx_state = {"learning_rate":mx.array(float(config["lr"]),dtype=mx.float32)}
    steps = set()
    for pid,key in zip(param_ids,keys):
        weight = model_weights[key]
        if str(weight.dtype) != "torch.float32":
            raise ValueError("MLX_NOT_FP32_NATIVE_MODEL")
        cell = optimizer_state["state"][pid]
        if set(cell) != {"step","exp_avg","exp_avg_sq"}:
            raise ValueError("MLX_UNEXPECTED_ADAMW_MOMENT_FIELDS")
        if tuple(cell["exp_avg"].shape) != tuple(weight.shape) or \
                tuple(cell["exp_avg_sq"].shape) != tuple(weight.shape):
            raise ValueError("MLX_MOMENTS_SHAPE_MISMATCH")
        count = int(cell["step"].item())
        steps.add(count)
        mlx_state[key] = {"m":mx.array(cell["exp_avg"].numpy(),dtype=mx.float32),
                          "v":mx.array(cell["exp_avg_sq"].numpy(),dtype=mx.float32)}
    if len(steps) != 1:
        raise ValueError("MLX_NATIVE_ADAMW_STEPS_DISAGREE")
    step = steps.pop()
    mlx_state["step"] = mx.array(step,dtype=mx.uint64)
    candidate = optim.AdamW(learning_rate=float(config["lr"]),
                            betas=list(config["betas"]),
                            eps=float(config["eps"]),
                            weight_decay=float(config["weight_decay"]),
                            bias_correction=True)
    candidate.state = mlx_state
    mx.eval(candidate.state)
    max_delta = 0.0
    for pid,key in zip(param_ids,keys):
        original = optimizer_state["state"][pid]
        restored = candidate.state[key]
        for old,new in (("exp_avg","m"),("exp_avg_sq","v")):
            delta = np.max(np.abs(original[old].numpy() - np.asarray(restored[new])))
            max_delta = max(max_delta,float(delta))
    if max_delta != 0.0 or int(candidate.state["step"].item()) != step:
        raise ValueError("MLX_COPIED_ADAMW_MOMENTS_DRIFT")
    return {"moment_entries":len(keys), "native_step":step,
            "max_moment_absolute_error":max_delta,
            "adamw_bias_correction":True,
            "native_optimizer_updated":False,
            "full_training_continuation_proven":False}, candidate


def probe(checkpoint: Path, legacy_source: Path, *, expected_sha256: str = AUDITED_PARENT.sha256):
    """Verify the exact historical student with the original loader on CPU."""
    import numpy as np
    import torch
    import mlx.core as mx
    from bilqis_development.continuation import load
    from bilqis_school import numeric_answer_contract as typed

    checkpoint = Path(checkpoint).resolve(strict=True)
    if digest_file(checkpoint) != expected_sha256:
        raise ValueError("MLX_HISTORICAL_SOURCE_SHA_MISMATCH")
    mx.set_default_device(mx.cpu)
    model,optimizer,payload = load(checkpoint)
    if payload["config"]["precision"] != "fp32":
        raise ValueError("MLX_PREVIOUS_STUDENT_NOT_FP32")
    model.eval()
    config = payload["config"]
    answer_ids = model.answer_ids.cpu().numpy().tolist()
    number_ids = typed.numeric_token_ids(payload["graph"])[:4]
    # Symbolic token IDs only. No fixed gold/assessment rows are touched.
    ids=np.array([[4,6,7,0],[6,7,8,9]],dtype=np.int64)
    lengths=np.array([3,4],dtype=np.int64)
    with torch.no_grad():
        baseline=model(torch.tensor(ids),torch.tensor(lengths)).numpy()
        numeric_reference=typed.readout(model,torch.tensor(ids),torch.tensor(lengths),
                                        answer_kind="numeric",number_ids=number_ids).numpy()
    tensors = {key: mx.array(value.detach().cpu().numpy(),dtype=mx.float32)
               for key,value in model.state_dict().items()}
    alt = forward(mx,tensors,ids,lengths,heads=config["heads"],
                  layers=config["layers"],answer_ids=answer_ids)
    maximum = float(np.max(np.abs(baseline-alt)))
    alt_numeric = forward(mx,tensors,ids,lengths,heads=config["heads"],
                          layers=config["layers"],answer_ids=number_ids)
    numeric_error = float(np.max(np.abs(numeric_reference-alt_numeric)))
    # Derive optimizer parameter order from original live Python parameter
    # objects, not from guessed positional matches of identical-sized tensors.
    names = {id(p): name for name,p in model.named_parameters()}
    order = tuple(names[id(p)] for p in optimizer.param_groups[0]["params"])
    moments,_unused = native_optimizer_to_mlx(
        optimizer.state_dict(),model.state_dict(),parameter_order=order)
    if max(maximum,numeric_error) > 2e-3:
        raise ValueError("MLX_FULL_CHECKPOINT_FORWARD_PARITY_OUTSIDE_TOLERANCE:"+str(maximum))
    return {"status":"FULL_FP32_FORWARD_AND_NATIVE_ADAMW_MOMENT_MAPPING_VERIFIED",
            "checkpoint_sha256":expected_sha256,
            "source_version":payload["version"],
            "config":config,
            "answer_ids":answer_ids,
            "integer_0_3_answer_ids":list(number_ids),
            "input_examples":len(ids),
            "forward_max_abs_error":maximum,
            "numeric_0_3_forward_max_abs_error":numeric_error,
            "forward_tolerance":2e-3,
            "optimizer":moments,
            "device":"cpu",
            "saved_student_written":False,
            "neural_optimizer_updates":0,
            "complete_optimizer_training_continuation_proven":False,
            "authorizes_neural_training":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint",required=True,type=Path)
    p.add_argument("--legacy-code-root",required=True,type=Path)
    args=p.parse_args(argv)
    source=args.legacy_code_root.resolve(strict=True)
    if not source.joinpath("bilqis_development","continuation.py").is_file():
        p.error("Not the original native checkpoint loader root")
    sys.path.insert(0,str(source))
    sys.dont_write_bytecode = True
    print(json.dumps(probe(args.checkpoint,source),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
