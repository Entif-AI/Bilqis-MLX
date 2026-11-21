"""Compatibility at the first candidate after objective identity was introduced."""
from dataclasses import replace

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import begin_candidate
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import parent_state
from bilqis_mlx.runtime.training_objective import current_training_objective


def test_historical_unbound_parent_binds_current_objective_for_new_candidate():
    parent = parent_state()
    historical = replace(
        parent,
        custody=replace(
            parent.custody,
            training_objective_ref=None,
            training_objective_digest=None,
        ),
    )

    candidate = begin_candidate(historical)

    objective = current_training_objective()
    assert candidate.training_objective_ref == objective.ref
    assert candidate.training_objective_digest == objective.digest
    assert historical.custody.training_objective_ref is None
    assert historical.custody.training_objective_digest is None


def test_present_mismatched_parent_objective_still_fails_closed():
    parent = parent_state()
    conflicting = replace(
        parent,
        custody=replace(parent.custody, training_objective_digest="f" * 64),
    )

    with pytest.raises(BilqisError):
        begin_candidate(conflicting)
