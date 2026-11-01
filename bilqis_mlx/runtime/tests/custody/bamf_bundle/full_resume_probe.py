"""Complete unbound numerical custody; never a source or admission witness."""
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, AdamWStateTree, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.backbone_group_numerical import run_backbone_group_numerical
from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state

STATUS = "UNBOUND_NUMERICAL_CUSTODY_ONLY"


def full_candidate():
    """Replace the tiny fixture's numerical tree with the entire actual B01 ledger."""
    template = candidate(parent_state())
    numerical, _, initialization = _create_unbound_bamf_optimizer(
        template.topology, template.extents, run_seed=479,
    )
    first, second, counts = dict(numerical.m), dict(numerical.v), dict(numerical.update_counts)
    name = "blocks.0.query"
    first[name] = mx.full(numerical.parameters[name].shape, 0.125, dtype=mx.float32)
    second[name] = mx.full(numerical.parameters[name].shape, 0.25, dtype=mx.float32)
    counts[name] = mx.array(5, dtype=mx.uint64)
    identity_counts = mx.array(counts["identity.bank.0"])
    for age in template.retained_state.policy.row_ages:
        identity_counts[age.row_index] = age.accepted_age
    counts["identity.bank.0"] = identity_counts
    numerical = AdamWStateTree(numerical.parameters, first, second, counts)
    retained = CandidateState(numerical, template.retained_state.policy,
                              template.retained_state.allocations, 12)
    hp = initialization["optimizer"]
    return replace(template, retained_state=retained,
                   optimizer_hyperparameters=AdamWHyperparameters(
                       hp["learning_rate"], tuple(hp["betas"]), hp["eps"], hp["weight_decay"]))


def _tree_digest(tree):
    digest = hashlib.sha256()
    for name, value in sorted(tree.items()):
        array = np.asarray(value)
        identity = json.dumps([name, array.dtype.str, array.shape], separators=(",", ":"))
        digest.update(identity.encode("utf-8"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def observe_bundle(root, manifest_digest):
    """Read every state byte and execute the same unadmitted numerical backbone."""
    student = load_bamf_bundle(root, expected_manifest_sha256=manifest_digest)
    return observe_student(student)


def observe_student(student):
    """Fingerprint the original candidate as well as detached cold-loaded state."""
    state = student.retained_state.optimizer
    mx.eval(state.parameters, state.m, state.v, state.update_counts)
    hidden = mx.linspace(-1, 1, 2 * student.topology.width).reshape(1, 2, -1)
    for index in range(1, student.topology.depth_groups + 1):
        result = run_backbone_group_numerical(
            hidden, state.parameters, group_index=index,
            spec=student.topology, extents=student.extents,
            scope_ids=mx.zeros((1, 2), dtype=mx.int32),
            valid=mx.ones((1, 2), dtype=mx.bool_),
            generation=student.topology.digest, prefix_digest="f" * 64,
        )
        hidden = result.hidden
    mx.eval(hidden)
    observation = {
        "status": STATUS,
        "run_id": student.run_id,
        "generation": student.generation,
        "parent_manifest_sha256": student.parent_manifest_sha256,
        "implementation_sha256": student.implementation_sha256,
        "optimizer_hyperparameters": asdict(student.optimizer_hyperparameters),
        "teacher_state": dict(student.teacher_state),
        "provenance": student.provenance.to_record(),
        "evaluation_contract": dict(student.evaluation_contract),
        "transition": dict(student.transition),
        "outbox_payloads": [{k: v for k, v in event.items() if k != "event_id"}
                            for event in student.outbox],
        "parameters_sha256": _tree_digest(state.parameters),
        "first_moments_sha256": _tree_digest(state.m),
        "second_moments_sha256": _tree_digest(state.v),
        "counts_sha256": _tree_digest(state.update_counts),
        "parameter_tensor_count": len(state.parameters),
        "parameter_count": sum(value.size for value in state.parameters.values()),
        "serialized_tensor_count": 4 * len(state.parameters),
        "backbone_output_sha256": _tree_digest({"hidden": hidden}),
        "backbone_output_finite": bool(np.isfinite(np.asarray(hidden)).all()),
        "topology_digest": student.topology.digest,
        "extent_digest": student.extents.digest,
        "optimizer_step": student.retained_state.optimizer_step,
        "policy": student.retained_state.policy.to_record(),
        "motif_digest": student.retained_state.allocations.digest,
        "teacher_next_seed": student.teacher_state["next_seed"],
        "teacher_cursor": student.teacher_state["cursor"],
        "semantic_abi": dict(student.semantic_abi),
        "compiler_features": dict(student.compiler_features),
        "correction_frontier": dict(student.correction_frontier),
    }

    return json.loads(json.dumps(observation, sort_keys=True))


if __name__ == "__main__":
    mx.set_default_device(mx.cpu)
    print(json.dumps(observe_bundle(Path(sys.argv[1]), sys.argv[2]), sort_keys=True))
