"""Issue-local intervention and exact B12 optimizer-state witness."""
from __future__ import annotations

import numpy as np

from bilqis_mlx.runtime.bamf_bundle import admission
from bilqis_mlx.learning.atlas_candidate import resolve_candidate


def selected_inputs(parent, mode):
    original, active = admission.derive_participation_inputs(parent)
    if original.mode != "FULL":
        raise AssertionError(f"expected genesis FULL control, found {original.mode}")
    selected = admission.group_eligibility(
        mode, admission._parameter_census(parent), parent.retained_state.policy.row_ages)
    assert selected.admitted_identity_rows == original.admitted_identity_rows
    return selected, active


def _assert_bytes(before, after, name):
    left, right = np.asarray(before), np.asarray(after)
    if (left.dtype != right.dtype or left.shape != right.shape
            or left.tobytes() != right.tobytes()):
        raise AssertionError(f"frozen optimizer state changed: {name}")


def verify_optimizer(parent, candidate, eligibility):
    """Compare actual native optimizer leaves, not just the reported mask."""
    before, after = parent.retained_state.optimizer, candidate.optimizer
    assert set(before.parameters) == set(after.parameters)
    frozen = set(eligibility.frozen_parameter_names)
    allowed_rows = set(eligibility.fast_identity_rows)
    proof = {"whole_frozen_leaves": 0, "unchanged_rows": 0,
             "changed_leaves": 0, "advanced_update_counts": 0,
             "frozen_nonzero_parameter_leaves": 0}
    for name, parameter in before.parameters.items():
        old, new = np.asarray(before.update_counts[name]), np.asarray(after.update_counts[name])
        assert np.all(new >= old), name
        delta = new - old
        assert np.all(delta <= candidate.update_steps), name
        proof["advanced_update_counts"] += int(np.count_nonzero(delta))
        proof["changed_leaves"] += int(np.any(delta != 0))
        whole = name in frozen and not name.startswith("identity.bank.")
        if whole:
            assert not np.any(delta), name
            proof["whole_frozen_leaves"] += 1
            proof["frozen_nonzero_parameter_leaves"] += int(np.any(np.asarray(parameter) != 0))
        # Count-zero rows must preserve weights, moments and decay. Identity
        # banks have row-dependent eligibility even when their name is frozen.
        untouched = delta == 0
        if old.ndim and old.shape[0] == parameter.shape[0]:
            if eligibility.mode == "FAST" and name.startswith("identity.bank."):
                bank = int(name.split(".")[-1])
                ineligible = np.array([(bank, row) not in allowed_rows for row in range(len(old))])
                assert np.all(untouched[ineligible]), name
            proof["unchanged_rows"] += int(np.count_nonzero(untouched))
        for tree_name in ("parameters", "m", "v", "update_counts"):
            a = getattr(before, tree_name)[name]
            b = getattr(after, tree_name)[name]
            if whole or np.all(untouched):
                _assert_bytes(a, b, f"{name}/{tree_name}")
            elif old.ndim and old.shape[0] == parameter.shape[0] and np.any(untouched):
                _assert_bytes(np.asarray(a)[untouched], np.asarray(b)[untouched],
                              f"{name}/{tree_name}/rows")
    assert proof["advanced_update_counts"] > 0
    if eligibility.mode == "FAST":
        assert proof["whole_frozen_leaves"] > 0
        assert proof["frozen_nonzero_parameter_leaves"] > 0
    assert resolve_candidate(candidate, accepted=False) is candidate.parent
    assert candidate.parent is parent.retained_state
    return {**proof, "rejection_returns_exact_parent": True}
