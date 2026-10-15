"""Pure teacher-only weighted model averaging from unique checkpoint tensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .champions import Checkpoint, soup_weights


@dataclass(frozen=True)
class TeacherSoup:
    weights: dict
    contributor_multiplicity: dict[str, int]
    kind: str = "FROZEN_TEACHER_WEIGHTS_ONLY"
    optimizer: None = None


def weighted_teacher(grade_champions: Mapping[str, Checkpoint],
                     unique_models: Mapping[str, Mapping[str, object]]) -> TeacherSoup:
    """Blend each distinct checkpoint *once* with its grade vote count.

    The caller is responsible for verifying checkpoint hashes on disk before
    loading tensors; this operation neither loads files nor saves checkpoints.
    It deliberately cannot yield an AdamW state.
    """
    import numpy as np
    multiplicity = soup_weights(dict(grade_champions))
    if not multiplicity or set(unique_models) != set(multiplicity):
        raise ValueError("SOUP_UNVERIFIED_OR_MISSING_CHAMPION_CONTRIBUTORS")
    keys = None
    arrays = {}
    for sha in sorted(multiplicity):
        model = unique_models[sha]
        if keys is None:
            keys = set(model)
        if not keys or set(model) != keys:
            raise ValueError("SOUP_MODEL_GEOMETRY_MISMATCH")
        cast = {name: np.asarray(arr) for name, arr in model.items()}
        if any(a.dtype != np.float32 or not np.isfinite(a).all() for a in cast.values()):
            raise ValueError("SOUP_NONFP32_OR_NONFINITE_WEIGHTS")
        arrays[sha] = cast
    output = {}
    total_votes = sum(multiplicity.values())
    for name in sorted(keys):
        expected = next(iter(arrays.values()))[name].shape
        if any(model[name].shape != expected for model in arrays.values()):
            raise ValueError("SOUP_PARAMETER_SHAPE_MISMATCH")
        total = np.zeros(expected, dtype=np.float64)
        for sha, weight in multiplicity.items():
            total += arrays[sha][name].astype(np.float64) * weight
        output[name] = np.asarray(total / total_votes, dtype=np.float32)
    return TeacherSoup(output, multiplicity)
