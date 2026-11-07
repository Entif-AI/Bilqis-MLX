"""Read a receiver and its address identities under the B13 pointer lock."""
from pathlib import Path

import numpy as np

from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle
from bilqis_mlx.runtime.bamf_bundle import publication

from .contracts import PackageBinding, require


def _load_current_generation(run_dir):
    run_dir = Path(run_dir)
    with publication._pointer_lock(run_dir):
        pointer = publication._read_pointer(run_dir / 'bamf-state.json')
        require(pointer is not None, 'receiver generation pointer missing')
        publication._live_bundle_manifest(run_dir, pointer)
        student = load_bamf_bundle(run_dir / pointer['bundle'],
                                   expected_manifest_sha256=pointer['manifest_sha256'])
        require(student.run_id == pointer['run_id']
                and student.generation == pointer['generation']
                and student.parent_manifest_sha256 == pointer['parent_manifest_sha256'],
                'receiver generation pointer drift')
        return pointer, student


def _receiver_tensors(student):
    from .delta import ReceiverTensor
    return tuple(ReceiverTensor(name, tuple(array.shape), array.tobytes())
                 for name, value in sorted(student.retained_state.optimizer.parameters.items())
                 for array in (np.asarray(value, dtype='<f4'),))


def _binding_for_student(student, tensors):
    from .delta import receiver_parameter_schema_digest, receiver_weight_digest
    return PackageBinding(
        receiver_weight_digest(tensors), receiver_parameter_schema_digest(tensors),
        student.topology.digest, student.provenance.release_digest,
        student.extents.active_semantic_digest, student.extents.factor_map_digest,
        student.extents.motif_key_map_digest)


def current_receiver_binding(run_dir):
    """Read the exact package compatibility identity from current B13 custody."""
    _, student = _load_current_generation(run_dir)
    tensors = _receiver_tensors(student)
    return _binding_for_student(student, tensors)


def apply_from_current_generation(package, run_dir):
    """Build a disposable delta against the exact locked published generation."""
    from .delta import _apply_delta_tensors, _issue_candidate

    pointer, student = _load_current_generation(run_dir)
    tensors = _receiver_tensors(student)
    binding = _binding_for_student(student, tensors)
    result = _apply_delta_tensors(package, binding, tensors)
    return _issue_candidate(pointer['manifest_sha256'], package, binding, tensors, result)
