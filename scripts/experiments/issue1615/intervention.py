"""Isolated B11 trie intervention and live participation observation."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, fields
from unittest.mock import patch
import time

import mlx.core as mx

from prefix_dag import SPEC, TrieLayout, block
from bilqis_mlx.runtime import atlas_model_microbatch as microbatch
from bilqis_mlx.runtime import backbone_group_numerical
from bilqis_mlx.runtime import factory_candidate_microbatch as c08
from bilqis_mlx.runtime.candidate.step_authority import require_learning_first_step_authority


@dataclass(frozen=True)
class ExperimentalGroup:
    """Only the live hidden is consumed by ordinary trace; no cache custody claimed."""
    hidden: mx.array


def layout_for(producer, *, gathered):
    if (not producer._trace or producer._input_motif_read is not None
            or producer._motif_manifest is not None or producer._source_execution_authorities is not None):
        return None
    compiled = producer._compiled
    rows = []
    vocabulary = {}
    for index, (row, config, source) in enumerate(zip(
            compiled.compiled.rows, compiled.compiler_configs, producer._sources, strict=True)):
        abi = source.learning_abi_indices
        if abi is None or len(abi) != row.visible_end:
            return None
        keys = []
        for position in row.positions:
            if position.kind.value == "ATOM":
                key = ("atom", abi[position.source_index])
            elif position.kind.value == "CLOSURE":
                key = ("private-closure", index, len(keys))
            else:
                raise AssertionError("unknown compiled position kind")
            keys.append(vocabulary.setdefault(key, len(vocabulary)))
        scope = (config.task.scope, source.source_row.get("capability"),
                 row.semantic_release, row.policy_version)
        rows.append((scope, tuple(keys)))
    return TrieLayout.build(tuple(rows), gathered=gathered)


def _producer_hook(original_producer, mode, counts):
    def producer(*args, **kwargs):
        result = original_producer(*args, **kwargs)
        value, accepted, _ = result
        if mode == "control":
            counts["eligible_batches"] += 1
            counts["logical_positions"] += sum(len(row.positions)
                                                for row in value._compiled.compiled.rows)
            counts["padded_positions"] += value._initial_hidden.shape[0] * value._initial_hidden.shape[1]
            return result
        started = time.perf_counter()
        layout = layout_for(value, gathered=mode == "gathered")
        counts["layout_construction_seconds"] += time.perf_counter() - started
        if layout is None or accepted is not None:
            counts["ineligible_batches"] += 1
            return result
        # The production encoder's padding is defined by exactly these rows.
        if layout.valid.shape != value._initial_hidden.shape[:2]:
            raise AssertionError("compiled layout/padding mismatch")
        value._session._issue1615_layout = layout
        counts["eligible_batches"] += 1
        counts["logical_positions"] += sum(len(row.positions)
                                            for row in value._compiled.compiled.rows)
        counts["unique_positions"] += len(layout.tokens)
        counts["padded_positions"] += layout.valid.size
        counts["layout_array_bytes"] += sum(
            getattr(layout, f.name).nbytes for f in fields(layout)
            if getattr(layout, f.name) is not None)
        counts["attention_mask_slots"] += (layout.ancestor_valid.size if mode == "gathered"
                                          else layout.allowed.size)
        return result
    return producer


def _advance_hook(original_advance, mode, counts):
    def advance(session, *, next_input=None):
        layout = getattr(session, "_issue1615_layout", None)
        if mode == "control" or layout is None or len(layout.tokens) >= layout.valid.size:
            return original_advance(session, next_input=next_input)
        group = len(session._results)
        if group >= SPEC.depth_groups:
            raise AssertionError("unexpected group")
        hidden = session._hidden if next_input is None else next_input
        if hidden.shape[:2] != layout.valid.shape:
            raise AssertionError("unexpected depth boundary shape")
        # Gather a representative only where the entire numerical causal history
        # is identical by construction. Gradients flow through that representative
        # and every reconstructed logical row, including multiplicities.
        current = hidden.reshape(-1, SPEC.width)[layout.representative]
        size = SPEC.layers // SPEC.depth_groups
        for layer in range(group * size, (group + 1) * size):
            prefix = f"blocks.{layer}."
            params = {key.removeprefix(prefix): value
                      for key, value in session._parameters.items() if key.startswith(prefix)}
            current = block(params, current, layout, shared=True, gathered=mode == "gathered")
        expanded = mx.where(layout.valid[..., None], current[layout.row_nodes], 0)
        result = ExperimentalGroup(expanded)
        session._hidden = expanded
        session._results += (result,)
        counts["shared_groups"] += 1
        counts["eliminated_block_positions"] += size * (layout.valid.size - len(layout.tokens))
        return result
    return advance


def _gradient_hook(original_gradient, counts, captures, capture_gradients):
    def gradient(params, row_batches, plans, *args, **kwargs):
        # A learning-first generation is a process-local capability, not a
        # content hash. Verify it with its actual owner before comparing arms.
        token = plans[0].generation_binding
        authority = require_learning_first_step_authority(token, parameters=params)
        result = original_gradient(params, row_batches, plans, *args, **kwargs)
        rows = []
        for item, plan in zip(result.executions, plans, strict=True):
            if item.generation_binding != token or plan.generation_binding != token:
                raise AssertionError("row participation is not bound to the live step")
            if item.motif_reads:
                raise AssertionError("motif-bearing trace is outside this experiment")
            rows.append({f.name: getattr(item, f.name) for f in fields(item)
                         if f.compare and f.name != "generation_binding"})
        coordinates = {name: getattr(authority, name) for name in (
            "accepted_run_id", "accepted_generation", "accepted_generation_binding",
            "accepted_candidate_identity_sha256", "release_sha256",
            "source_authority_registry_sha256", "topology_digest", "extents_digest",
            "optimizer_step", "candidate_step", "speculative")}
        captures.append({"loss": float(result.mean_loss),
                         "gradients": dict(result.gradients) if capture_gradients else {},
                         "participation": rows, "authority": coordinates,
                         "validated_local_token": token})
        counts["vectorized_launches"] += 1
        return result
    return gradient


@contextmanager
def instrument(mode, counts, captures, capture_gradients):
    producer = _producer_hook(microbatch._source_producer, mode, counts)
    advance = _advance_hook(backbone_group_numerical.BackboneTraceSession.advance, mode, counts)
    gradient = _gradient_hook(c08.bamf_microbatch_value_and_grad, counts, captures, capture_gradients)

    with patch.object(microbatch, "_source_producer", producer), patch.object(
            backbone_group_numerical.BackboneTraceSession, "advance", advance), patch.object(
            c08, "bamf_microbatch_value_and_grad", gradient):
        yield
