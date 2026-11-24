"""R14 native rehearsal planning, custody, and provenance contracts."""
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_training_contracts import BamfDeliveryProvenance
from bilqis_mlx.runtime.factory_training_preparation import _target_source_count
from bilqis_mlx.runtime.bamf_operator.session_parts.rehearsal import (
    RehearsalPlan, RehearsalRows, _seed, compile_rehearsal_plan,
    materialize_rehearsal_rows,
)
from bilqis_mlx.runtime.bamf_operator.source_prefetch import (
    prepare_priority_source_packet, priority_source_request,
)
from bilqis_mlx.runtime.factory_candidate_training import FactoryDeliveryObservation
from bilqis_mlx.runtime.accepted_priority_visit import (
    execute_accepted_priority_candidate,
)
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.runtime.source_prefetch import thaw_source_packet
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import (
    visit_provenance,
)
from bilqis_mlx.semantic_sampling import DEFAULT_BINARY_BALANCE
from bilqis_mlx.semantics.domains import contract_digest


def test_plan_is_grade_neutral_and_partitions_authorized_relationships():
    from bilqis_mlx.runtime.retention.protection_plan import (
        ProtectionReason,
    )
    target = NS(
        target_grade_id="GENERATED-ZETA",
        protected_capability_ids=("Z.C0", "Z.C1"),
        affected_edges=(
            NS(capability_id="Z.C0", reason=ProtectionReason.PREREQUISITE),
            NS(capability_id="Z.C1", reason=ProtectionReason.DEPENDENT),
        ),
    )
    protection = NS(digest="a" * 64)
    active = NS(
        member_capability_ids=("Z.C2",), activation_sha256="f" * 64,
        definition=NS(definition_sha256="1" * 64))
    release = NS(execution_plan=NS(capability_map={
        "Z.C2": NS(grade_id="GENERATED-ZETA")
    }))
    weakness = {
        "weakness_evidence_sha256": "b" * 64,
        "evidence_kind": "SCORED_PARENT_MISS",
        "context": {"context_sha256": "1" * 64},
        "weakness_class": {
            "provider_id": "provider:z", "provider_implementation_sha256": "c" * 64,
            "classifier_id": "classifier:z", "classifier_sha256": "d" * 64,
            "structural_signature": {"shape": "novel"}, "class_sha256": "e" * 64,
        },
    }
    with patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.rehearsal.require_current_retention_plan",
            return_value=(protection, target)), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.rehearsal.current_structural_weaknesses",
            return_value=({"weakness": weakness},)), patch(
            "bilqis_mlx.runtime.active_generated_grade.read_active_generated_grade",
            return_value=active):
        plan = compile_rehearsal_plan(
            "/run", object(), object(), NS(release=release),
            NS(offer=NS(capability_id="Z.C2", source_each=4)))

    assert plan.target_capability_id == "Z.C2"
    assert plan.target_grade_id == "GENERATED-ZETA"
    assert plan.prior_capability_ids == ("Z.C0",)
    assert plan.retention_support_capability_ids == ("Z.C1",)
    assert plan.weakness_records == (weakness,)
    assert plan.active_grade_definition_sha256 == "1" * 64
    assert plan.active_grade_activation_sha256 == "f" * 64


class _BoundSourceContext:
    def execution_for(self, capability):
        return NS(
            provider_id="provider:" + capability,
            provider_implementation_sha256=contract_digest({"capability": capability}),
        )

    def draw_bound_rows(self, *, seed, capability, each):
        if each != DEFAULT_BINARY_BALANCE.minimum_total:
            from bilqis_mlx._source_evidence.live_grade_a import draw_predicates
            draw_predicates(None, {}, seed=seed, each=each)
        rows = tuple({
            "id": f"{capability}:{seed}:{index}", "capability": capability,
            "source_family_id": f"family:{capability}",
            "episode_id": f"episode:{seed}:{index}",
            "tokens": [seed, index], "gold": "TRUE" if index % 2 else "FALSE",
        } for index in range(each))
        authority = NS(
            capability_id=capability, seed=seed, each=each,
            source_family_id=rows[0]["source_family_id"],
        )
        return rows, authority

    def bind_authorized_subset_rows(self, parent_rows, selected_rows, authority):
        assert authority.each == len(parent_rows) == DEFAULT_BINARY_BALANCE.minimum_total
        assert len(selected_rows) == 1
        assert selected_rows[0] in parent_rows
        return NS(
            capability_id=authority.capability_id, seed=authority.seed, each=1,
            source_family_id=authority.source_family_id,
        )


def test_materialization_retains_one_row_source_authority_per_rehearsal_specimen():
    plan = RehearsalPlan(
        "Z.C2", "GENERATED-ZETA", ("Z.C0",), ("Z.C1",), (),
        "a" * 64, "c" * 64, "d" * 64, "b" * 64)
    rows = materialize_rehearsal_rows(_BoundSourceContext(), plan, 3)

    assert tuple(row["capability"] for row in rows.prior) == ("Z.C0",)
    assert tuple(row["capability"] for row in rows.retention_support) == ("Z.C1",)
    assert set(rows.bindings_by_id) == set(rows.authorities_by_id)
    for identity, binding in rows.bindings_by_id.items():
        authority = rows.authorities_by_id[identity]
        assert binding["seed"] == authority.seed
        assert binding["each"] == authority.each == 1
        assert binding["capability"] == authority.capability_id


def test_rehearsal_specimen_selection_uses_seed_not_provider_row_zero():
    plan = RehearsalPlan(
        "Z.C2", "GENERATED-ZETA", ("Z.C0",), (), (),
        "a" * 64, "c" * 64, "d" * 64, "b" * 64)
    context = _BoundSourceContext()
    ordinal = next(
        value for value in range(32)
        if _seed(plan, "prior", "Z.C0", value)
        % DEFAULT_BINARY_BALANCE.minimum_total != 0)

    rows = materialize_rehearsal_rows(context, plan, ordinal)

    row = rows.prior[0]
    expected_seed = _seed(plan, "prior", "Z.C0", ordinal)
    expected_index = expected_seed % DEFAULT_BINARY_BALANCE.minimum_total
    assert row["id"].endswith(f":{expected_index}")
    assert expected_index != 0


def test_preservation_selects_one_matching_row_from_balanced_source_draw():
    from bilqis_mlx.source_adapters.lesson_geometry import LessonGeometry
    weakness_record = {"weakness_class": {"class_sha256": "wanted"},
                       "context": {"context_sha256": "context"},
                       "historical_source_ids": []}
    plan = RehearsalPlan(
        "Z.C2", "GENERATED-ZETA", (), (), (weakness_record,),
        "a" * 64, "c" * 64, "d" * 64, "b" * 64, weakness_capacity=1)
    context = _BoundSourceContext()

    def classify(_adapter, _execution, row, *, provider_descriptor):
        del provider_descriptor
        return NS(class_sha256=(
            "wanted" if row["id"].endswith(":2") else "other"))

    with patch(
            "bilqis_mlx.runtime.structural_weakness_capture._provider_for_context",
            return_value=(object(), object(), object())), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.weakness_rehearsal."
            "geometry_for_adapter", return_value=LessonGeometry("singleton")), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.weakness_rehearsal.classify_weakness",
            side_effect=classify):
        rows = materialize_rehearsal_rows(context, plan, 3)

    assert len(rows.preservation) == 1
    row = rows.preservation[0]
    assert row["id"].endswith(":2")
    binding = rows.bindings_by_id[row["id"]]
    authority = rows.authorities_by_id[row["id"]]
    assert binding["role"] == "preservation"
    assert binding["weakness_debt_key"] == "context:wanted"
    assert rows.weakness_unavailable == ()
    assert binding["each"] == authority.each == 1
    assert binding["seed"] == authority.seed


def test_candidate_delivery_receipts_actual_rehearsal_roles():
    candidate_owner = sys.modules[execute_accepted_priority_candidate.__module__]
    direct = ({"id": "direct", "capability": "Z.C2"},)
    prior = {"id": "prior", "capability": "Z.C0"}
    preservation = {"id": "preservation", "capability": "Z.C2"}
    support = {"id": "support", "capability": "Z.C1"}
    rehearsal = (prior, preservation, support)
    roles = {
        prior["id"]: "prior",
        preservation["id"]: "preservation",
        support["id"]: "retention_support",
    }
    bindings = {identity: {"row_id": identity} for identity in roles}
    authorities = {identity: object() for identity in roles}
    offer = NS(
        capability_id="Z.C2", source_seed=17, rows=lambda: direct,
    )
    selection = NS(offer=offer)
    release = NS(execution_plan=NS(capability_map={
        "Z.C2": NS(teaching_option_ids=("instruction",)),
    }))
    capture = NS(
        attempt_id="attempt", proposal_id="proposal", selected_option="instruction",
        delivery=lambda *_args, **_kwargs: None,
    )
    observation = FactoryDeliveryObservation(capture, 1, direct, 17)

    with patch.object(candidate_owner, "describe_delivered_teaching", return_value="delivery"):
        result = candidate_owner._candidate_delivery_inputs(
            selection, NS(release=release), direct, (), rehearsal, roles,
            bindings, authorities, observation)

    realized = result[-1]
    assert realized.prior == (prior,)
    assert realized.preservation == (preservation,)
    assert realized.support == (support,)
    assert realized.controls["fragile_preservation_delivered"] == 1
    assert realized.controls["retention_support_delivered"] == 1
    import bilqis_mlx.learning.learning_experiment as experiment
    action = experiment.realized_teacher_action(
        {"lr": .0001, "old": 20, "distill": 0.}, candidate_steps=1,
        batch_size=len((*direct, *rehearsal)), policy_controls=(realized.controls,),
        guidance_applied_steps=0, enrichment_examples=0)
    assert action["features"]["fragile_preservation_delivered"] == 1
    assert action["features"]["retention_support_delivered"] == 1
    assert action["features"]["old_grade_examples_delivered"] == 0


def test_worker_packet_transports_roles_but_not_process_live_authority():
    direct = ({"id": "Z.C2:direct", "capability": "Z.C2"},)
    prior = ({"id": "Z.C0:prior", "capability": "Z.C0"},)
    binding = {
        "row_id": "Z.C0:prior", "role": "prior", "capability": "Z.C0",
        "seed": 31, "each": 1, "source_family_id": "family:Z.C0",
        "episode_id": "episode:31",
    }
    rehearsal = RehearsalRows(prior=prior, bindings=(binding,), authorities=((prior[0]["id"], object()),))
    source_binding = {"capability": "Z.C2", "provider": "fixture"}
    offer = NS(
        accepted_manifest_sha256="a" * 64, generation_binding="b" * 64,
        release_sha256="c" * 64, capability_id="Z.C2", source_seed=17,
        source_each=1, source_family_id="family:Z.C2",
        source_binding_digest=contract_digest(source_binding),
        source_authority=NS(content_sha256=source_content_digest(direct)),
        rows=lambda: direct,
    )
    selection = NS(offer=offer, visit=NS(identity=NS(visit_id="visit:z")))
    release = NS(
        release_sha256="c" * 64,
        source_bindings=NS(by_capability={"Z.C2": source_binding}))
    request = priority_source_request(
        selection, NS(release=release), NS(retained_state=NS(optimizer_step=7)), 1,
        enrichment_rows=(), rehearsal_plan=NS(identity="d" * 64), rehearsal=rehearsal)
    packet = prepare_priority_source_packet(request)
    payload = thaw_source_packet(packet)

    assert payload["prior"] == list(prior)
    assert "rehearsal_bindings" not in payload
    assert request["rehearsal_bindings"] == [binding]
    assert "authorities" not in request


def _delivery_provenance(row_capability, rehearsal):
    row = {"id": "row:z", "capability": row_capability}
    return BamfDeliveryProvenance(
        row["id"], source_content_digest((row,)), None, row_capability, None,
        (), 1, 1, rehearsal, 0, visit_provenance("Z.C2"), "family:z", "episode:z")


def test_cross_capability_delivery_requires_explicit_rehearsal_role():
    assert _delivery_provenance("Z.C0", "prior").rehearsal == "prior"
    with pytest.raises(BilqisError) as failure:
        _delivery_provenance("Z.C0", None)
    assert failure.value.context["reason"] == "VISIT_PROVENANCE_CAPABILITY_MISMATCH"


def test_rehearsal_rows_do_not_inflate_target_source_batch_count():
    rows = (
        {"id": "target", "capability": "Z.C2"},
        {"id": "prior", "capability": "Z.C0"},
        {"id": "enrichment", "capability": "Z.C2"},
    )
    assert _target_source_count(rows, {"prior": "prior"}) == 2

