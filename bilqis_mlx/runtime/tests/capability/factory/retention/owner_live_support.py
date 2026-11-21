"""Stable façade for disposable source-owned C05 witness mechanics."""

# Expensive live witnesses importing this module must still be launched through
# scripts/bamf/detached_long_run.py rather than an interactive test session.

from .owner_live_candidate_support import (
    TARGET, TRAIN_SEED, _execute_source_owned_candidate_step_evidence,
    _source_owned_candidate_step, _source_owned_candidate_step_evidence,
    _teacher_selected_source_owned_candidate_step_evidence,
)
from .owner_live_generation_support import (
    _assert_published_generation_one, _initialize_generation,
    _publish_c05_successor, _publish_disposable_source_qualified_successor,
)


__all__ = (
    "TARGET", "TRAIN_SEED", "_assert_published_generation_one",
    "_execute_source_owned_candidate_step_evidence", "_initialize_generation",
    "_publish_c05_successor", "_publish_disposable_source_qualified_successor",
    "_source_owned_candidate_step", "_source_owned_candidate_step_evidence",
    "_teacher_selected_source_owned_candidate_step_evidence",
)
