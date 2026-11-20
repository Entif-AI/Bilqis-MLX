"""Recovery exhaustion never invents future generated-grade authority."""
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime.tests.teacher.priority.authority.test_priority_signer import (
    _foundation_case,
)


def test_recovery_exhaustion_keeps_priority_inside_active_generated_grade():
    from bilqis_mlx.runtime import priority_authority as authority

    (registry, signer, source_context, planning, parent,
     planning_generation, offer, cache, lawful) = _foundation_case()
    exhausted = SimpleNamespace(
        authorized_capability_ids=(),
        phase=SimpleNamespace(value="BOUNDARY"),
        disposition=SimpleNamespace(value="RECOVERY_EXHAUSTED"),
    )
    with patch(
        "bilqis_mlx.runtime.bamf_bundle.accepted_runtime._accepted_correction_registry",
        return_value=(cache, registry),
    ), patch(
        "bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer."
        "read_host_system_source_authority_signer", return_value=signer,
    ), patch.object(
        authority, "bind_priority_planning_generation", return_value=planning_generation,
    ), patch.object(
        authority, "_require_planning_generation", return_value=(cache, None),
    ), patch.object(
        authority, "prepare_priority_source_offer", side_effect=offer,
    ), patch.object(
        authority, "priority_rotation_state", return_value=(1, {}),
    ), patch.object(
        authority, "_build_priority_planning_epoch", return_value="epoch",
    ), patch.object(
        authority, "_priority_planning_from_epoch", return_value=planning,
    ), patch(
        "bilqis_mlx.runtime.lawful_teaching_frontier."
        "_issue_lawful_teaching_frontier_from_epoch", return_value=lawful,
    ), patch(
        "bilqis_mlx.runtime.active_grade_cadence.issue_active_grade_cadence",
        return_value=exhausted,
    ), patch.object(
        authority, "_ordered_rejections", return_value=(),
    ), patch.object(
        authority, "_rejection_recency", return_value=(0, {}),
    ):
        issued = authority.issue_foundation_priority_authority(
            "/run", source_context, parent, {"epoch": 1}, "/atlas",
            teacher_state=parent.teacher_state)

    assert issued.cadence is exhausted
    assert issued.selection_cadence is exhausted
    assert issued.lawful_frontier is lawful
    assert issued.frontier is None
    assert issued.history is None
    assert issued.offers == ()
