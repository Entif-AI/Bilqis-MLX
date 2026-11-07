"""Native AdamW counts and fail-closed historical count migration.

No durable student, participation-policy decision, generation publication, or
legacy-v1-to-BAMF generation coercion is implemented by this numerical seam.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import mlx.core as mx
import mlx.optimizers as optim
import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.mlx_parity import clip_gradients


ROW_COUNT_RANK = 1
ADAM_MOMENT_COUNT = 2
UINT64_MAX = int(np.iinfo(np.uint64).max)
STATE_SCHEMA = "bilqis.mlx.adamw-count-state/provisional-v1"
HISTORICAL_MIGRATION_SCHEMA = "bilqis.mlx.historical-adamw-migration-capability/v1"
HISTORICAL_ATTESTATION_SCHEMA = "bilqis.mlx.historical-adamw-update-attestation/v1"
HISTORICAL_FULL_TREE_CONTRACT = (
    "bilqis.mlx.historical-full-tree-shared-scalar-static-count-geometry/v1"
)
_HISTORICAL_MIGRATION_ISSUER = object()
_HISTORICAL_ATTESTATION_FIELDS = frozenset({
    "schema", "architecture_id", "checkpoint_sha256", "model_state_sha256",
    "optimizer_state_sha256", "count_geometry_sha256", "global_optimizer_step",
    "update_contract",
})

# Deliberately empty until a BAMF-v2-compatible historical generation has an
# audited whole-lineage proof. The pinned six-layer v1 parent is readable
# evidence, but B01/B13 explicitly forbid coercing it into a v2 generation.
_HISTORICAL_UPDATE_ATTESTATIONS = MappingProxyType({})


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _is_sha256(value):
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


@dataclass(frozen=True)
class AdamWHyperparameters:
    """Exact supplied teacher values; this record makes no policy selection."""

    learning_rate: float
    betas: tuple[float, float]
    eps: float
    weight_decay: float

    def __post_init__(self):
        if (not _finite_number(self.learning_rate) or self.learning_rate <= 0 or
                type(self.betas) is not tuple or len(self.betas) != ADAM_MOMENT_COUNT or
                any(not _finite_number(beta) or not 0 <= beta < 1 for beta in self.betas) or
                not _finite_number(self.eps) or self.eps <= 0 or
                not _finite_number(self.weight_decay) or self.weight_decay < 0):
            _invalid()


@dataclass(frozen=True)
class AdamWStateTree:
    """One exact numerical tree; dense counts are scalar, table counts per row.

    uint64 scalar counts give whole-tensor participation. A uint64 vector whose
    length equals the parameter's leading extent gives per-row participation.
    The normative runtime/model_topology_v2.py parameter ledger, row admission
    and serialization must be bound by the complete-model and candidate
    transaction owners before this fixture tree becomes candidate state.
    """

    parameters: Mapping[str, mx.array]
    m: Mapping[str, mx.array]
    v: Mapping[str, mx.array]
    update_counts: Mapping[str, mx.array]
    schema_version: str = STATE_SCHEMA

    def __post_init__(self):
        self.validate()
        for name in ("parameters", "m", "v", "update_counts"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    def validate(self):
        """Inspect without rewriting the parent, including rejected/no-loss calls."""
        trees = (self.parameters, self.m, self.v, self.update_counts)
        if (self.schema_version != STATE_SCHEMA or any(not isinstance(tree, Mapping) for tree in trees) or
                not self.parameters or any(type(name) is not str or not name for name in self.parameters) or
                any(set(tree) != set(self.parameters) for tree in trees)):
            _invalid()
        for name, parameter in self.parameters.items():
            if (not isinstance(parameter, mx.array) or parameter.dtype != mx.float32 or
                    parameter.size < 1):
                _invalid()
            for moment in (self.m[name], self.v[name]):
                if not isinstance(moment, mx.array) or moment.shape != parameter.shape or moment.dtype != mx.float32:
                    _invalid()
            count = self.update_counts[name]
            if (not isinstance(count, mx.array) or count.dtype != mx.uint64 or
                    not (count.shape == () or (parameter.ndim >= ROW_COUNT_RANK and
                                              count.shape == (parameter.shape[0],)))):
                _invalid()
            if (not all(bool(mx.all(mx.isfinite(value))) for value in (parameter, self.m[name], self.v[name])) or
                    not bool(mx.all(self.v[name] >= 0))):
                _invalid()


@dataclass(frozen=True, init=False)
class HistoricalAdamWMigrationCapability:
    """Ephemeral authority to expand one proven shared scalar into B12 counts.

    This capability is intentionally non-serializable and caller construction
    is forbidden. It binds one exact checkpoint and detached numerical state to
    one code-owned whole-history update contract.
    """

    attestation_id: str
    architecture_id: str
    checkpoint_sha256: str
    model_state_sha256: str
    optimizer_state_sha256: str
    count_geometry_sha256: str
    global_optimizer_step: int
    update_contract: str
    schema_version: str
    _issuance: object

    def __init__(self, *args, **kwargs):
        _invalid()

    def __post_init__(self):
        from bilqis_mlx.runtime.model_topology_v2 import BAMF_ARCHITECTURE_ID

        if (getattr(self, "_issuance", None) is not _HISTORICAL_MIGRATION_ISSUER
                or not isinstance(self.attestation_id, str) or not self.attestation_id
                or self.architecture_id != BAMF_ARCHITECTURE_ID
                or any(not _is_sha256(value) for value in (
                    self.checkpoint_sha256, self.model_state_sha256,
                    self.optimizer_state_sha256, self.count_geometry_sha256))
                or type(self.global_optimizer_step) is not int
                or not 0 <= self.global_optimizer_step <= UINT64_MAX
                or self.update_contract != HISTORICAL_FULL_TREE_CONTRACT
                or self.schema_version != HISTORICAL_MIGRATION_SCHEMA):
            _invalid()


def _validate_step_inputs(parent, gradients, participation):
    if (type(parent) is not AdamWStateTree or
            any(not isinstance(tree, Mapping) or set(tree) != set(parent.parameters)
                for tree in (gradients, participation))):
        _invalid()
    parent.validate()
    for name, parameter in parent.parameters.items():
        gradient, mask = gradients[name], participation[name]
        if (not isinstance(gradient, mx.array) or gradient.shape != parameter.shape or gradient.dtype != mx.float32 or
                not bool(mx.all(mx.isfinite(gradient))) or
                not isinstance(mask, mx.array) or mask.dtype != mx.bool_ or
                mask.shape != parent.update_counts[name].shape):
            _invalid()


def _preflight(parent, gradients, participation, hyperparameters, decay, loss_bearing):
    _validate_step_inputs(parent, gradients, participation)
    if (type(hyperparameters) is not AdamWHyperparameters or type(loss_bearing) is not bool or
            not isinstance(decay, Mapping) or set(decay) != set(parent.parameters) or
            any(type(value) is not bool for value in decay.values())):
        _invalid()
    hyperparameters.__post_init__()
    for name, count in parent.update_counts.items():
        if loss_bearing and bool(mx.any(participation[name] &
                                       (count == mx.array(np.array(UINT64_MAX, dtype=np.uint64))))):
            _invalid()


def _masked_clipped_gradients(parent, gradients, participation, *, max_norm):
    """Mask supplied participation before the existing global FP32 norm clip.

    This numerical adapter does not attest that masks came from actual model
    execution. The full-model owner must supply that independent provenance.
    """
    _validate_step_inputs(parent, gradients, participation)
    if not _finite_number(max_norm) or max_norm <= 0:
        _invalid()
    masked = {}
    for name, gradient in gradients.items():
        mask = participation[name]
        if mask.ndim == ROW_COUNT_RANK:
            mask = mask.reshape((-1,) + (1,) * (gradient.ndim - 1))
        masked[name] = mx.where(mask, gradient, mx.zeros_like(gradient))
    clipped, norm = clip_gradients(mx, masked, max_norm=max_norm)
    if not bool(mx.isfinite(norm)):
        _invalid()
    return clipped, norm


def _adamw_update(parent: AdamWStateTree, gradients: Mapping[str, mx.array],
                  participation: Mapping[str, mx.array], hyperparameters: AdamWHyperparameters, *,
                  decay: Mapping[str, bool], loss_bearing: bool = True,
                  max_norm: float | None = None) -> AdamWStateTree:
    """Apply native AdamW only to selected numerical leaves/rows, without publication.

    max_norm uses the existing global clip after participation masking. When
    omitted, supplied gradients must already follow the clipping contract.
    Masks are explicit Boolean scalars or row vectors, never inferred from
    nonzero gradients. Selected zero gradients still advance moments/counts.
    No-loss and wholly frozen steps return the original state object.
    """
    _preflight(parent, gradients, participation, hyperparameters, decay, loss_bearing)
    if max_norm is not None and (not _finite_number(max_norm) or max_norm <= 0):
        _invalid()
    if not loss_bearing or not any(bool(mx.any(mask)) for mask in participation.values()):
        return parent
    if max_norm is not None:
        gradients, _ = _masked_clipped_gradients(parent, gradients, participation, max_norm=max_norm)
    parameters, first, second, counts = (dict(tree) for tree in
                                         (parent.parameters, parent.m, parent.v, parent.update_counts))
    for name, parameter in parent.parameters.items():
        mask = participation[name]
        if not bool(mx.any(mask)):
            continue
        count = parent.update_counts[name]
        rowwise = count.ndim == ROW_COUNT_RANK
        indices = mx.array(np.flatnonzero(np.asarray(mask)), dtype=mx.uint32) if rowwise else None
        selected = lambda value: value[indices] if rowwise else value
        next_count = selected(count) + 1
        step = next_count.reshape((-1,) + (1,) * (parameter.ndim-1)) if rowwise else next_count
        optimizer = optim.AdamW(learning_rate=hyperparameters.learning_rate, betas=hyperparameters.betas,
                                eps=hyperparameters.eps,
                                weight_decay=hyperparameters.weight_decay if decay[name] else 0,
                                bias_correction=True)
        optimizer.state = {"step": step, "learning_rate": mx.array(hyperparameters.learning_rate, dtype=mx.float32)}
        cell = {"m": selected(parent.m[name]), "v": selected(parent.v[name])}
        updated = optimizer.apply_single(selected(gradients[name]), selected(parameter), cell)
        for target, original, replacement in (
                (parameters, parameter, updated),
                (first, parent.m[name], cell["m"]),
                (second, parent.v[name], cell["v"])):
            if rowwise:
                candidate = mx.array(original)
                candidate[indices] = replacement
                target[name] = candidate
            else:
                target[name] = replacement
        counts[name] = count + mask.astype(mx.uint64) if rowwise else next_count
    return AdamWStateTree(parameters, first, second, counts)


def _declared_update_count_shape(item) -> tuple[int, ...]:
    """Derive B12 count geometry from the B01 initializer ledger only."""
    from bilqis_mlx.runtime.model_topology_v2 import Initializer, MATRIX_RANK

    table_initializers = {
        Initializer.IDENTITY_BANK,
        Initializer.MOTIF_PAGE,
        Initializer.FEATURE_TABLE,
    }
    rowwise = (
        item.initializer in table_initializers
        or (item.initializer is Initializer.EMBEDDING and len(item.shape) == MATRIX_RANK)
    )
    return (item.shape[0],) if rowwise else ()


def _canonical_digest(value) -> str:
    try:
        wire = json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        _invalid()
    return hashlib.sha256(wire).hexdigest()


def _parameter_order_tuple(parameter_order, model_weights) -> tuple[str, ...]:
    try:
        names = tuple(parameter_order)
    except TypeError:
        _invalid()
    if (not isinstance(model_weights, Mapping) or not names
            or any(type(name) is not str or not name for name in names)
            or len(names) != len(set(names)) or set(names) != set(model_weights)):
        _invalid()
    return names


def _historical_model_state_digest(model_weights, *, parameter_order) -> str:
    """Digest exact ordered native FP32 weights without serializing authority."""
    names = _parameter_order_tuple(parameter_order, model_weights)
    digest = hashlib.sha256()
    for name in names:
        value = model_weights[name]
        try:
            array = np.ascontiguousarray(value.detach().cpu().numpy())
        except (AttributeError, TypeError, ValueError):
            _invalid()
        if str(value.dtype) != "torch.float32" or array.dtype != np.float32:
            _invalid()
        digest.update(json.dumps(
            [name, list(array.shape), str(array.dtype)],
            separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        digest.update(b"\0")
        digest.update(array.tobytes(order="C"))
        digest.update(b"\0")
    return digest.hexdigest()


def _historical_optimizer_state_digest(
        optimizer_state, model_weights, *, parameter_order) -> str:
    """Digest native AdamW hyperparameters, moments and per-parameter steps."""
    names = _parameter_order_tuple(parameter_order, model_weights)
    if (not isinstance(optimizer_state, Mapping)
            or set(optimizer_state) != {"state", "param_groups"}
            or not isinstance(optimizer_state["state"], Mapping)
            or type(optimizer_state["param_groups"]) is not list
            or len(optimizer_state["param_groups"]) != 1):
        _invalid()
    group = optimizer_state["param_groups"][0]
    if not isinstance(group, Mapping):
        _invalid()
    param_ids = group.get("params")
    if (type(param_ids) is not list or len(param_ids) != len(names)
            or len(param_ids) != len(set(param_ids))
            or set(optimizer_state["state"]) != set(param_ids)):
        _invalid()
    config = {name: value for name, value in group.items() if name != "params"}
    digest = hashlib.sha256()
    digest.update(json.dumps(
        config, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8"))
    digest.update(b"\0")
    for pid, name in zip(param_ids, names):
        cell = optimizer_state["state"][pid]
        if not isinstance(cell, Mapping) or set(cell) != {"step", "exp_avg", "exp_avg_sq"}:
            _invalid()
        try:
            step_array = np.asarray(cell["step"].detach().cpu().numpy())
            step_value = float(step_array.item())
            first = np.ascontiguousarray(cell["exp_avg"].detach().cpu().numpy())
            second = np.ascontiguousarray(cell["exp_avg_sq"].detach().cpu().numpy())
        except (AttributeError, TypeError, ValueError, OverflowError):
            _invalid()
        if (step_array.shape != () or not math.isfinite(step_value)
                or step_value < 0 or step_value > UINT64_MAX
                or step_value != math.floor(step_value)):
            _invalid()
        step = int(step_value)
        weight = model_weights[name]
        if (step < 0 or tuple(first.shape) != tuple(weight.shape)
                or tuple(second.shape) != tuple(weight.shape)
                or first.dtype != np.float32 or second.dtype != np.float32):
            _invalid()
        digest.update(json.dumps(
            [name, step, str(step_array.dtype), list(step_array.shape), list(first.shape)],
            separators=(",", ":"),
            ensure_ascii=False).encode("utf-8"))
        digest.update(b"\0")
        digest.update(step_array.tobytes(order="C"))
        digest.update(b"\0")
        digest.update(first.tobytes(order="C"))
        digest.update(b"\0")
        digest.update(second.tobytes(order="C"))
        digest.update(b"\0")
    return digest.hexdigest()


def _historical_count_geometry_digest(declared) -> str:
    """Bind the historical contract to the exact B01 count geometry."""
    try:
        items = tuple(declared)
        record = [{
            "name": item.name,
            "parameter_shape": list(item.shape),
            "count_shape": list(_declared_update_count_shape(item)),
        } for item in items]
    except (AttributeError, TypeError, ValueError):
        _invalid()
    if not items or len({item["name"] for item in record}) != len(record):
        _invalid()
    return _canonical_digest(record)


def _checkpoint_digest(path) -> str:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        _invalid()
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        _invalid()
    return digest.hexdigest()


def _historical_update_attestation(attestation_id):
    from bilqis_mlx.runtime.model_topology_v2 import BAMF_ARCHITECTURE_ID

    if type(attestation_id) is not str or not attestation_id:
        _invalid()
    attestation = _HISTORICAL_UPDATE_ATTESTATIONS.get(attestation_id)
    if (not isinstance(attestation, Mapping)
            or set(attestation) != _HISTORICAL_ATTESTATION_FIELDS
            or attestation.get("schema") != HISTORICAL_ATTESTATION_SCHEMA
            or attestation.get("architecture_id") != BAMF_ARCHITECTURE_ID
            or attestation.get("update_contract") != HISTORICAL_FULL_TREE_CONTRACT
            or not all(_is_sha256(attestation.get(name)) for name in (
                "checkpoint_sha256", "model_state_sha256",
                "optimizer_state_sha256", "count_geometry_sha256"))
            or type(attestation.get("global_optimizer_step")) is not int
            or not 0 <= attestation["global_optimizer_step"] <= UINT64_MAX):
        _invalid()
    return attestation


def _mint_historical_bamf_migration_capability(
        checkpoint_path, optimizer_state, model_weights, *, parameter_order,
        spec, extents, attestation_id):
    """Issue ephemeral migration authority only from a code-owned attestation.

    An attestation asserts the strong historical fact B12.3 needs: every count
    entry in one static B01 geometry existed for the complete scalar lineage and
    participated in every optimizer step. Equal terminal native counters are
    checked for consistency, but never treated as that authority by themselves.
    """
    from bilqis_mlx.runtime.model_topology_v2 import (
        BAMF_ARCHITECTURE_ID, GenerationExtents, ModelTopologySpecV2,
        expected_bamf_shapes,
    )
    from bilqis_mlx.runtime.mlx_parity import native_optimizer_to_mlx

    if (type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(attestation_id) is not str or not attestation_id):
        _invalid()
    attestation = _historical_update_attestation(attestation_id)
    declared = expected_bamf_shapes(spec, extents)
    names = _parameter_order_tuple(parameter_order, model_weights)
    if (names != tuple(item.name for item in declared)
            or any(tuple(model_weights[item.name].shape) != item.shape
                   for item in declared)):
        _invalid()
    checkpoint_sha256 = _checkpoint_digest(checkpoint_path)
    model_sha256 = _historical_model_state_digest(
        model_weights, parameter_order=names)
    optimizer_sha256 = _historical_optimizer_state_digest(
        optimizer_state, model_weights, parameter_order=names)
    geometry_sha256 = _historical_count_geometry_digest(declared)
    try:
        receipt, _ = native_optimizer_to_mlx(
            optimizer_state, model_weights, parameter_order=names)
    except (KeyError, TypeError, ValueError):
        _invalid()
    if (checkpoint_sha256 != attestation["checkpoint_sha256"]
            or model_sha256 != attestation["model_state_sha256"]
            or optimizer_sha256 != attestation["optimizer_state_sha256"]
            or geometry_sha256 != attestation["count_geometry_sha256"]
            or receipt.get("native_step") != attestation["global_optimizer_step"]):
        _invalid()
    capability = object.__new__(HistoricalAdamWMigrationCapability)
    for name, value in (
        ("attestation_id", attestation_id),
        ("architecture_id", BAMF_ARCHITECTURE_ID),
        ("checkpoint_sha256", checkpoint_sha256),
        ("model_state_sha256", model_sha256),
        ("optimizer_state_sha256", optimizer_sha256),
        ("count_geometry_sha256", geometry_sha256),
        ("global_optimizer_step", attestation["global_optimizer_step"]),
        ("update_contract", HISTORICAL_FULL_TREE_CONTRACT),
        ("schema_version", HISTORICAL_MIGRATION_SCHEMA),
        ("_issuance", _HISTORICAL_MIGRATION_ISSUER),
    ):
        object.__setattr__(capability, name, value)
    capability.__post_init__()
    return capability


def _migrate_historical_bamf_optimizer(
        optimizer_state, model_weights, *, parameter_order, spec, extents,
        capability):
    """Map one attested all-together historical scalar into B12 counts.

    This is a detached numerical migration seam, not permission to coerce a v1
    bundle into a v2 generation. Native counter equality is only a consistency
    check. Whole-lineage participation authority comes from the exact-state,
    code-owned capability issued above.
    """
    from bilqis_mlx.runtime.model_topology_v2 import (
        GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    )
    from bilqis_mlx.runtime.mlx_parity import native_optimizer_to_mlx

    if (type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(capability) is not HistoricalAdamWMigrationCapability):
        _invalid()
    capability.__post_init__()
    attestation = _historical_update_attestation(capability.attestation_id)
    for field in (
            "architecture_id", "checkpoint_sha256", "model_state_sha256",
            "optimizer_state_sha256", "count_geometry_sha256",
            "global_optimizer_step", "update_contract"):
        if getattr(capability, field) != attestation[field]:
            _invalid()
    declared = expected_bamf_shapes(spec, extents)
    names = tuple(item.name for item in declared)
    ordered = _parameter_order_tuple(parameter_order, model_weights)
    if (ordered != names
            or any(tuple(model_weights[item.name].shape) != item.shape
                   for item in declared)):
        _invalid()
    model_sha256 = _historical_model_state_digest(
        model_weights, parameter_order=ordered)
    optimizer_sha256 = _historical_optimizer_state_digest(
        optimizer_state, model_weights, parameter_order=ordered)
    geometry_sha256 = _historical_count_geometry_digest(declared)
    if (model_sha256 != capability.model_state_sha256
            or optimizer_sha256 != capability.optimizer_state_sha256
            or geometry_sha256 != capability.count_geometry_sha256):
        _invalid()
    try:
        receipt, mapped = native_optimizer_to_mlx(
            optimizer_state, model_weights, parameter_order=ordered)
    except (KeyError, TypeError, ValueError):
        _invalid()
    step = receipt.get("native_step")
    if (type(step) is not int or step != capability.global_optimizer_step
            or not 0 <= step <= UINT64_MAX):
        _invalid()
    try:
        parameters = {
            item.name: mx.array(
                model_weights[item.name].detach().cpu().numpy(), dtype=mx.float32)
            for item in declared
        }
        first = {item.name: mapped.state[item.name]["m"] for item in declared}
        second = {item.name: mapped.state[item.name]["v"] for item in declared}
        counts = {
            item.name: mx.full(
                _declared_update_count_shape(item), step, dtype=mx.uint64)
            for item in declared
        }
    except (AttributeError, KeyError, TypeError, ValueError):
        _invalid()
    state = AdamWStateTree(parameters, first, second, counts)
    mx.eval(state.parameters, state.m, state.v, state.update_counts)
    return state, {
        **receipt,
        "historical_attestation_id": capability.attestation_id,
        "historical_checkpoint_sha256": capability.checkpoint_sha256,
        "historical_update_contract": capability.update_contract,
        "historical_all_parameters_updated_together": True,
        "b12_count_entries": len(counts),
    }


def _create_unbound_bamf_optimizer(spec, extents, *, run_seed):
    """Reuse the complete topology owner's disposable initialization verbatim.

    This fresh UNBOUND state has no admitted source rows or production caller.
    It is not a historical optimizer migration or a checkpoint-generation grant.
    Count geometry follows declared table initializers; vector seeds and dense
    matrices retain scalar counts. Decay flags come only from the same ledger.
    """
    from bilqis_mlx.runtime.model_topology_v2 import (
        create_unbound_bamf_state, expected_bamf_shapes,
    )

    parameters, native, manifest = create_unbound_bamf_state(spec, extents, run_seed=run_seed)
    declared = expected_bamf_shapes(spec, extents)
    counts = {
        item.name: mx.zeros(_declared_update_count_shape(item), dtype=mx.uint64)
        for item in declared
    }
    state = AdamWStateTree(parameters, {item.name: native[item.name]["m"] for item in declared},
                           {item.name: native[item.name]["v"] for item in declared}, counts)
    decay = MappingProxyType({item.name: item.decay for item in declared})
    return state, decay, manifest
