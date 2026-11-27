"""Native numerical counterfactuals and bounded, leafwise interference analysis."""
from contextlib import ExitStack
from collections import defaultdict
import math

import mlx.core as mx
import numpy as np
from safetensors import safe_open

from bilqis_mlx.runtime.atlas_optimizer import _adamw_update
from bilqis_mlx.runtime.atlas_optimizer_preflight import _masked_clipped_gradients
from bilqis_mlx.runtime.optimizer_step import adamw_leaf_update, adamw_selected_rows_update
from scripts.bamf.profiling.issue1645.frozen_displacement import OUTPUT_LEAVES, EPSILON_CANDIDATES
from scripts.bamf.profiling.issue1645.reservation import require
from scripts.bamf.profiling.issue1645.dynamics.artifacts import require_full_basis, sha256_file


def group(name):
    if name in OUTPUT_LEAVES:
        return "dedicated_readout"
    if name.startswith("identity.bank."):
        return "tied_identity"
    return "other_shared_parameters"


def expanded(array, parameter):
    return array.reshape((-1,) + (1,) * (parameter.ndim - 1)) if array.ndim else array


def leaf(parent, name, gradient, mask, hp, decay, eps, rows=None):
    arguments = (parent.parameters[name], parent.m[name], parent.v[name],
                 parent.update_counts[name], gradient, mask)
    kwargs = dict(learning_rate=hp.learning_rate, betas=hp.betas, eps=eps,
                  weight_decay=hp.weight_decay if decay else 0.)
    if rows:
        return adamw_selected_rows_update(*arguments, rows, **kwargs)
    return adamw_leaf_update(*arguments, **kwargs)


def components(parent, name, gradient, mask, hp, decay):
    """Analytic old-moment and decay components using actual next v and row clock.

    FP32 actual displacement is the reference; remaining displacement contains
    the current-gradient component and numerical rounding.
    """
    weight = parent.parameters[name]
    count = parent.update_counts[name] + mask.astype(mx.uint64)
    selected = expanded(mask, weight)
    safe_count = expanded(mx.where(mask, count, mx.ones_like(count)), weight)
    b1, b2 = hp.betas
    next_v = b2 * parent.v[name] + (1 - b2) * mx.square(gradient)
    c1 = (hp.learning_rate / (1 - b1**safe_count)).astype(weight.dtype)
    c2 = mx.rsqrt(1 - b2**safe_count).astype(weight.dtype)
    old = -c1 * b1 * parent.m[name] / (mx.sqrt(next_v) * c2 + hp.eps)
    decay_step = weight * (1 - hp.learning_rate * hp.weight_decay) - weight if decay else mx.zeros_like(weight)
    return mx.where(selected, old, 0.), mx.where(selected, decay_step, 0.)


def check_leaf(parent, result, name, expected, mask):
    maxima = {}
    for field, reference in zip(("parameters", "m", "v", "update_counts"), expected, strict=True):
        actual = np.asarray(getattr(result, field)[name])
        wanted = np.asarray(reference)
        if field == "update_counts":
            require(np.array_equal(actual, wanted), f"clock mismatch: {name}")
            maxima[field] = 0.
        else:
            require(np.allclose(actual, wanted, rtol=2e-6, atol=1e-7),
                    f"native/full-mask mismatch: {name}/{field}")
            maxima[field] = float(np.max(np.abs(actual - wanted)))
        old = np.asarray(getattr(parent, field)[name])
        require(np.array_equal(actual[~mask], old[~mask]), f"frozen drift: {name}/{field}")
    return maxima


def checked_gradient_basis(parameters, gradients, masks=None, authority=None):
    require(bool(gradients) and set(gradients) <= set(parameters), "parameter basis mismatch")
    if masks is not None or authority is not None:
        require(set(parameters) == set(masks) == set(authority), "participation basis mismatch")
    omitted = sorted(set(parameters) - set(gradients))
    for name in omitted:
        require(masks is not None and authority is not None
                and authority[name] == (False, ()) and not bool(mx.any(masks[name]).item()),
                f"missing participating gradient: {name}")
    for name, value in gradients.items():
        require(value.shape == parameters[name].shape, "gradient shape mismatch")
    finite = [mx.all(mx.isfinite(value)) for value in gradients.values()]
    mx.eval(*finite)
    require(all(bool(item.item()) for item in finite), "nonfinite gradient")
    return omitted


def complete_protected_gradient(parameters, gradients, masks, authority):
    omitted = checked_gradient_basis(parameters, gradients, masks, authority)
    return {name: gradients[name] if name in gradients else mx.zeros_like(weight)
            for name, weight in parameters.items()}, omitted


def write_update(destination, parent, gradients, masks, decay, authority, hp, *, max_norm):
    require(set(parent.parameters) == set(decay), "decay basis mismatch")
    omitted = checked_gradient_basis(parent.parameters, gradients, masks, authority)
    destination.mkdir()
    clipped, norm = _masked_clipped_gradients(parent, gradients, masks, max_norm=max_norm)
    result = _adamw_update(parent, gradients, masks, hp, decay=decay, max_norm=max_norm,
                           participation_authority=authority, learning_first=True)
    mx.eval(*result.parameters.values(), *result.m.values(),
            *result.v.values(), *result.update_counts.values())
    arrays = {}
    records = {}
    equivalence = defaultdict(float)
    for name, weight in parent.parameters.items():
        mask = masks[name]
        host_mask = np.asarray(mask)
        # Native learning-first gradients may omit completely frozen leaves.
        # Zero extension is for the common diagnostic coordinate basis only.
        raw = gradients[name] if name in gradients else mx.zeros_like(weight)
        effective = clipped[name] if name in clipped else mx.zeros_like(weight)
        reference = leaf(parent, name, effective, mask, hp, decay[name], hp.eps)
        mx.eval(*reference)
        errors = check_leaf(parent, result, name, reference, host_mask)
        for field, error in errors.items():
            equivalence[field] = max(equivalence[field], error)
        delta = result.parameters[name] - weight
        old, decay_step = components(parent, name, effective, mask, hp, decay[name])
        arrays.update({f"raw/{name}": raw, f"clipped/{name}": effective,
                       f"delta/{name}": delta, f"old_moment/{name}": old,
                       f"decay/{name}": decay_step, f"mask/{name}": mask})
        for eps in EPSILON_CANDIDATES:
            if name in OUTPUT_LEAVES:
                alternate = leaf(parent, name, effective, mask, hp, decay[name], eps,
                                 authority[name][1])
                mx.eval(*alternate)
                for field, value in zip(("m", "v", "update_counts"), alternate[1:], strict=True):
                    require(np.array_equal(np.asarray(value), np.asarray(getattr(result, field)[name])),
                            f"epsilon changed optimizer history: {name}/{field}")
                arrays[f"eps{eps}/{name}"] = alternate[0] - weight
        mx.eval(*[value for key, value in arrays.items() if key.endswith("/" + name)])
        records[name] = {"group": group(name), "shape": list(weight.shape),
                         "selected_clocks": int(host_mask.sum()),
                         "total_clocks": int(host_mask.size),
                         "selected_rows": list(authority[name][1]),
                         "whole_parameter": bool(authority[name][0]), "decay": bool(decay[name])}
    mx.save_safetensors(str(destination / "update.safetensors"), arrays)
    return {"artifact_sha256": {"update.safetensors": sha256_file(destination / "update.safetensors")},
            "masked_unclipped_norm": float(norm.item()), "max_norm": max_norm,
            "selected_full_mask_max_abs_error": dict(equivalence),
            "leaves": records, "epsilon_candidates": list(EPSILON_CANDIDATES),
            "omitted_frozen_gradient_leaves": omitted}


def finalize(acc):
    acc = dict(acc)
    for metric in ("raw", "delta", "protected"):
        acc[f"{metric}_l2"] = math.sqrt(acc[f"{metric}_norm_sq"])
    denom = acc["raw_l2"] * acc["protected_l2"]
    acc["raw_gradient_cosine"] = acc["raw_gradient_dot"] / denom if denom else None
    acc["current_gradient_and_rounding_dot"] = (
        acc["native_delta_dot"] - acc["old_moment_dot"] - acc["decay_dot"])
    return acc


def interference_matrix(destination, capabilities, protected_destination=None,
                        protected_capabilities=None, *, basis):
    """Read one leaf at a time, amortizing FP64 conversion over protected probes."""
    results = {}
    protected_destination = destination if protected_destination is None else protected_destination
    protected_capabilities = capabilities if protected_capabilities is None else protected_capabilities
    if not capabilities:
        return results
    with ExitStack() as stack:
        updates = {cap: stack.enter_context(safe_open(
            str(destination / cap / "update.safetensors"), framework="numpy"))
                   for cap in capabilities}
        protected = {cap: stack.enter_context(safe_open(
            str(protected_destination / cap / "protected.safetensors"), framework="numpy"))
                     for cap in protected_capabilities}
        require(bool(basis) and bool(protected), "empty diagnostic basis")
        for item in updates.values():
            require_full_basis(item, basis, update=True)
        for item in protected.values():
            require_full_basis(item, basis)
        names = sorted(basis)
        totals = {(a, b): defaultdict(lambda: defaultdict(float))
                  for a in capabilities for b in protected_capabilities}
        for name in names:
            shape = tuple(basis[name])
            def coordinates(source, key):
                value = source.get_tensor(key)
                require(value.shape == shape, "parameter shape mismatch")
                return value.reshape(-1).astype(np.float64)
            probes = np.stack([coordinates(item, name) for item in protected.values()])
            require(np.isfinite(probes).all(), "nonfinite protected coordinates")
            protected_sq = np.einsum("ij,ij->i", probes, probes)
            for target, source in updates.items():
                raw, clipped, delta, old, decay = (
                    coordinates(source, f"{kind}/{name}")
                    for kind in ("raw", "clipped", "delta", "old_moment", "decay"))
                alternatives = {eps: coordinates(source, f"eps{eps}/{name}")
                                if name in OUTPUT_LEAVES else delta for eps in EPSILON_CANDIDATES}
                vectors = {"raw_gradient_dot": raw, "raw_negative_gradient_dot": -raw,
                           "clipped_negative_gradient_dot": -clipped, "native_delta_dot": delta,
                           "old_moment_dot": old, "decay_dot": decay,
                           **{f"epsilon_{eps}_delta_dot": v for eps, v in alternatives.items()}}
                require(all(v.size == probes.shape[1] and np.isfinite(v).all()
                            for v in vectors.values()), "invalid target coordinates")
                dots = {key: probes @ value for key, value in vectors.items()}
                raw_sq, delta_sq = float(raw @ raw), float(delta @ delta)
                for i, cap in enumerate(protected_capabilities):
                    for bucket in ("all", group(name)):
                        acc = totals[target, cap][bucket]
                        for key, values in dots.items():
                            acc[key] += float(values[i])
                        acc["raw_norm_sq"] += raw_sq
                        acc["delta_norm_sq"] += delta_sq
                        acc["protected_norm_sq"] += float(protected_sq[i])
        for (target, cap), buckets in totals.items():
            results[f"{target}->{cap}"] = {key: finalize(value) for key, value in buckets.items()}
    return results
