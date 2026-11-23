"""Fresh teacher mutations remain replayable without weakening compact custody."""
from copy import deepcopy
import random
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bilqis_mlx.compatibility import historical_teacher_policy as engine
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.learning.teacher_strategy_population import effective_policy_key
from bilqis_mlx.runtime import state
from bilqis_mlx.runtime.bamf_operator.evidence_parts import CandidateEvidenceCapture
from bilqis_mlx.runtime.outcomes import replay
from bilqis_mlx.runtime.outcomes.observations import apply_outcome
from bilqis_mlx.runtime.teacher_policy_selection import select_visit_policy
from bilqis_mlx.runtime.tests.teacher.outcomes.test_outcome_credit import (
    outcome, teacher_fixture,
)


def test_compact_mutated_teacher_accepts_only_exact_verified_recovery():
    parent = teacher_fixture()
    selected = deepcopy(parent)
    selected["strategies"]["mutant"] = {
        **selected["strategies"]["policy"], "lr": .0002}
    selected["global_stats"]["mutant"] = engine._stats()
    compact = outcome(selected)
    compact.pop("selected_teacher")
    compact["teacher_visit"]["policy_key"] = "mutant"
    compact["selected_policy"] = deepcopy(selected["strategies"]["mutant"])
    compact["effective_policy_key"] = effective_policy_key(
        compact["selected_policy"])
    compact["selected_teacher_sha256"] = state._fingerprint(selected)
    compact["outcome_sha256"] = state._fingerprint(
        {key: value for key, value in compact.items()
         if key != "outcome_sha256"})

    with pytest.raises(BilqisError):
        apply_outcome(parent, compact)
    credited = apply_outcome(
        parent, compact, selected_teacher_override=selected)
    assert credited["global_stats"]["mutant"]["trials"] == 1

    drifted = deepcopy(selected)
    drifted["mutations"] += 1
    with pytest.raises(BilqisError):
        apply_outcome(
            parent, compact, selected_teacher_override=drifted)


def test_compact_fresh_mutation_reconstructs_exact_selected_teacher():
    teacher = teacher_fixture()
    for ordinal in range(1, 5):
        teacher = apply_outcome(
            teacher, outcome(
                teacher, ordinal, capability="A.TEST", grade="A"))
    selected = deepcopy(teacher)
    school = SimpleNamespace(
        stage="MAIN", current_student=SimpleNamespace(sha256="c" * 64))
    key, policy, metadata = select_visit_policy(
        engine, selected, "A.TEST", school, random.Random(1), Settings(),
        "factory/test", {}, "A", total_capabilities=21)
    assert metadata["selection_reason"] == "FRESH_MUTATED_CHALLENGER"
    diagnostic_key = metadata["diagnostic_context_key"]
    diagnostics = deepcopy(
        selected["causal_experiment"]["diagnostic_contexts"][diagnostic_key])

    compact = outcome(selected, 5, capability="A.TEST", grade="A")
    compact.pop("selected_teacher")
    compact["teacher_visit"].update(
        policy_key=key, selection_seed=1, student_sha256="c" * 64)
    compact["context"].update(
        phase="MAIN", curriculum_scope="factory/test",
        diagnostics=diagnostics, diagnostic_context_key=diagnostic_key,
        factory_release_sha256="f" * 64)
    compact["selected_policy"] = deepcopy(policy)
    compact["effective_policy_key"] = effective_policy_key(policy)
    compact["selected_teacher_sha256"] = state._fingerprint(selected)
    compact["outcome_sha256"] = state._fingerprint(
        {name: value for name, value in compact.items()
         if name != "outcome_sha256"})

    with patch.object(replay, "_factory_capability_count", return_value=21):
        recovered = replay._selected_teacher_override(
            "unused", teacher, compact)

    assert recovered == selected
    credited = apply_outcome(
        teacher, compact, selected_teacher_override=recovered)
    assert credited["global_stats"][key]["trials"] == 1


def test_future_mutated_selection_embeds_selected_teacher_snapshot(tmp_path):
    selected = teacher_fixture()
    identity = SimpleNamespace(
        visit_id="visit", policy_key="policy",
        to_record=lambda: {"visit_id": "visit", "policy_key": "policy"})
    projection = SimpleNamespace(
        teacher_state={"c03_lineage": {"current_teacher_sha256": "d" * 64}})
    selection = SimpleNamespace(
        option_id="option", visit=SimpleNamespace(
            identity=identity, projection=projection),
        offer=SimpleNamespace(
            capability_id="A.TEST", source_seed=1, release_sha256="f" * 64),
        policy=deepcopy(selected["strategies"]["policy"]),
        metadata={
            "how_context": {},
            "selected_teacher_snapshot_required": True,
        })
    with patch(
            "bilqis_mlx.runtime.bamf_operator.evidence_parts.capture.restore_teacher_lineage",
            return_value=SimpleNamespace(teacher=lambda: selected)):
        capture = CandidateEvidenceCapture(
            tmp_path, selection, generation=1,
            accepted_manifest_sha256="a" * 64,
            candidate_attempt_ordinal=1, parent_optimizer_step=0)
    assert capture.proposal["selected_teacher"] == selected
    assert "selected_teacher_sha256" not in capture.proposal
