"""#1590 learning-first fresh-support depth realization contracts."""
from types import SimpleNamespace as NS

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.source_execution import (
    SourceBatchAuthority, _bind_authorized_subset_rows, _draw_bound_rows,
    _require_bound_rows,
)
from bilqis_mlx.runtime.bamf_operator.session_parts.fresh_support import (
    DEEP_FRESH_SUPPORT_CONTROL,
    NO_REPLAY_CONTEXT,
    SHALLOW_FRESH_SUPPORT_CONTROL,
    materialize_fresh_support,
    require_fresh_support_authority,
)


class _FreshSupportContext:
    def __init__(self, capability, rows):
        self.capability = capability
        self.rows = tuple(rows)
        execution = NS(
            capability_id=capability,
            provider_id="provider:grade-a",
            provider_implementation_sha256="a" * 64,
        )
        self.release = NS(
            release_sha256="b" * 64,
            execution_plan=NS(capability_map={capability: execution}),
        )

    def require_capabilities(self, capabilities):
        assert capabilities == (self.capability,)

    def draw_bound_rows(self, *, seed, capability, each):
        assert capability == self.capability
        assert each == 4
        return _draw_bound_rows(self, seed=seed, capability=capability, each=each)

    def draw_rows(self, *, seed, capability, each):
        del seed
        assert capability == self.capability
        assert each == 4
        return self.rows

    def bind_authorized_subset_rows(self, parent_rows, selected_rows, authority):
        return _bind_authorized_subset_rows(
            self, parent_rows, selected_rows, authority)

    def require_bound_rows(self, rows, authority):
        return _require_bound_rows(self, rows, authority)


def _selection(capability, *, depth):
    return NS(
        policy={"lr": 0.001, "depth": depth},
        offer=NS(capability_id=capability),
        visit=NS(identity=NS(visit_id="visit:fresh-support")),
    )


def _replay_plan():
    return NS(
        prior_capability_ids=(), retention_support_capability_ids=(),
        weakness_records=({"weakness": "present"},),
    )


def test_deep_fresh_support_selects_longest_distinct_singleton_with_exact_authority():
    capability = "A.C0"
    direct = tuple({"id": f"direct:{index}"} for index in range(32))
    rows = (
        {"id": "short", "source_id": "short", "capability": capability,
         "tokens": [1], "episode_id": "ep:short"},
        {"id": "long", "source_id": "long", "capability": capability,
         "tokens": [1, 2, 3, 4], "episode_id": "ep:long"},
        {"id": "medium", "source_id": "medium", "capability": capability,
         "tokens": [1, 2], "episode_id": "ep:medium"},
        {"id": "other", "source_id": "other", "capability": capability,
         "tokens": [1, 2, 3], "episode_id": "ep:other"},
    )
    context = _FreshSupportContext(capability, rows)

    specimen = materialize_fresh_support(
        context, _selection(capability, depth=3), _replay_plan(), 1,
        reserved_rows=direct)

    assert tuple(row["id"] for row in specimen.rows) == ("long",)
    assert specimen.depth_control == DEEP_FRESH_SUPPORT_CONTROL
    assert specimen.unavailable_reason is None
    assert type(specimen.authority) is SourceBatchAuthority
    assert specimen.binding["role"] == "fresh_support"
    assert specimen.binding["row_id"] == "long"
    assert specimen.binding["each"] == 1
    assert require_fresh_support_authority(context, specimen) is specimen.authority


def test_fresh_support_binding_tamper_fails_local_authority_check():
    capability = "A.C0"
    rows = tuple({
        "id": f"row:{index}", "source_id": f"row:{index}",
        "capability": capability, "tokens": list(range(index + 1)),
        "episode_id": f"ep:{index}",
    } for index in range(4))
    context = _FreshSupportContext(capability, rows)
    specimen = materialize_fresh_support(
        context, _selection(capability, depth=3), _replay_plan(), 1,
        reserved_rows=())
    object.__setattr__(specimen, "binding", {**specimen.binding, "provider_id": "tampered"})

    with pytest.raises(BilqisError) as failure:
        require_fresh_support_authority(context, specimen)
    assert failure.value.context["reason"] == "BAMF_FRESH_SUPPORT_AUTHORITY_INVALID"


def test_shallow_depth_is_realized_without_adding_support_row():
    capability = "A.C0"
    rows = tuple({
        "id": f"row:{index}", "source_id": f"row:{index}",
        "capability": capability, "tokens": list(range(index + 1)),
        "episode_id": f"ep:{index}",
    } for index in range(4))
    specimen = materialize_fresh_support(
        _FreshSupportContext(capability, rows),
        _selection(capability, depth=2), _replay_plan(), 1, reserved_rows=())

    assert specimen.rows == ()
    assert specimen.authority is None
    assert specimen.binding is None
    assert specimen.depth_control == SHALLOW_FRESH_SUPPORT_CONTROL
    assert specimen.unavailable_reason is None


def test_deep_depth_without_replay_context_reports_unavailable_not_realized():
    capability = "A.C0"
    rows = tuple({
        "id": f"row:{index}", "source_id": f"row:{index}",
        "capability": capability, "tokens": list(range(index + 1)),
        "episode_id": f"ep:{index}",
    } for index in range(4))
    empty_plan = NS(
        prior_capability_ids=(), retention_support_capability_ids=(),
        weakness_records=(),
    )
    specimen = materialize_fresh_support(
        _FreshSupportContext(capability, rows),
        _selection(capability, depth=3), empty_plan, 1, reserved_rows=())

    assert specimen.rows == ()
    assert specimen.depth_control is None
    assert specimen.unavailable_reason == NO_REPLAY_CONTEXT
