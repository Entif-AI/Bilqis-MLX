"""Additional C16.3 operator routing and rejection contracts."""
from contextlib import ExitStack, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_operator.session import _visit, operate_bamf
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode


def _evidence_receipt():
    return {
        "schema": "bilqis.bamf.c16.3-candidate-evidence-reference/v1",
        "persistence": {
            "bytes_written": 300, "file_fsyncs": 1,
            "directory_fsyncs": 1, "evidence_objects": 4,
            "persistence_seconds": 0.005,
        },
    }


def _assert_rejected_resource(case, resource):
    case.assertEqual(resource["schema"], "bilqis.bamf.c16.3-resource-observation/v2")
    case.assertEqual(resource["evidence_bytes_written"], 300)
    case.assertEqual(resource["evidence_file_fsyncs"], 1)
    case.assertEqual(resource["evidence_directory_fsyncs"], 1)
    case.assertEqual(resource["evidence_objects"], 4)
    case.assertEqual(resource["evidence_persistence_seconds"], 0.005)


def _rejection_routing_fixture():
    parent = SimpleNamespace(
        retained_state=SimpleNamespace(optimizer_step=11),
        optimizer_hyperparameters="hparams")
    identity = SimpleNamespace(
        visit_id="visit:beta", policy_key="policy:beta",
        to_record=lambda: {"visit_id": "visit:beta"})
    selection = SimpleNamespace(
        status="TEACHER_SELECTED", option_id="capability:beta",
        visit=SimpleNamespace(
            identity=identity,
            projection=SimpleNamespace(teacher_state={
                "last_visit_receipt": {"schema": "fixture-receipt"}})),
        offer=SimpleNamespace(
            capability_id="capability:beta", source_seed=17,
            rows=lambda: ({"id": "row:1"},)))
    step = SimpleNamespace(
        transaction=SimpleNamespace(
            parent=SimpleNamespace(optimizer_step=11),
            update_steps=1, training_authorities=("authority",)),
        realized_cost={
            "wall_seconds": 1.0, "optimizer_steps": 1,
            "candidate_optimizer_steps": 1, "c08_memory_budget_bytes": 1})
    decision = SimpleNamespace(
        accepted=False, reason="retention_gate",
        to_record=lambda: {"decision": "REJECTED"})
    cache = SimpleNamespace(generation=1, accepted_manifest_sha256="a" * 64)
    return SimpleNamespace(
        parent=parent, context=SimpleNamespace(
            release=object(),
            _accepted_runtime_host=SimpleNamespace(_accepted_cache=cache)),
        selection=selection, step=step, decision=decision,
        capture=SimpleNamespace(finalize=lambda **_kwargs: _evidence_receipt()),
        cache=cache,
        evaluation=SimpleNamespace(
            candidate_state=object(), parent_state=parent.retained_state))


def _run_rejection_routing_fixture(case):
    prefix = "bilqis_mlx.runtime.bamf_operator.session."
    native = "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
    patches = (
        (prefix + "_execution_context",
         {"return_value": (case.parent, case.context, "atlas", "feature")}),
        (prefix + "schedule_program_from_executable_release", {"return_value": "program"}),
        (prefix + "accepted_priority_school", {"return_value": "school"}),
        (prefix + "select_foundation_priority_visit", {"return_value": case.selection}),
        (native + "bind_accepted_execution_cache", {
            "side_effect": AssertionError("learning-first routing must use session cache")}),
        ("bilqis_mlx.runtime.bamf_operator.session_parts.prepare_visit."
         "bind_current_retention_protection_plan", {"return_value": "plan"}),
        (native + "bind_current_retention_source_rows", {"return_value": "rows"}),
        (native + "rejection_attempt_ordinals", {"return_value": (1, 1)}),
        (native + "candidate_step_horizon", {"return_value": 1}),
        (native + "prepare_candidate_evidence_root", {}),
        (native + "_Capture", {"return_value": case.capture}),
        (native + "FactoryDeliveryObservation", {"return_value": "observation"}),
        (native + "execute_learning_first_priority_candidate", {"return_value": case.step}),
        (native + "evaluate_factory_retention_candidate", {"return_value": case.evaluation}),
        (native + "issue_factory_retention_decision", {"return_value": case.decision}),
    )
    with ExitStack() as stack:
        for target, kwargs in patches:
            stack.enter_context(patch(target, **kwargs))
        rejection = stack.enter_context(patch(prefix + "record_bamf_rejection"))
        with evidence_mode(strict=False):
            result = _visit(Path("/tmp"), 0.0)
    return result, rejection.call_args.args[2]


class _FactoryOrderTrap:
    @property
    def capabilities(self):
        raise AssertionError("bamf_operator must not inspect Factory capability order")


def _c03_selection_fixture():
    case = _rejection_routing_fixture()
    case.context.release = SimpleNamespace(execution_plan=_FactoryOrderTrap())
    return case


@patch("bilqis_mlx.runtime.bamf_operator.session._training_memory_context", nullcontext)
class BamfOperatorRoutingContinuationTests(unittest.TestCase):
    def setUp(self):
        for name, behavior in (
                ('build_outcome', {'return_value': {'schema': 'routing-fixture'}}),
                ('credited_visit', {'side_effect': lambda visit, outcome: visit}),
                ('carry_credit_to_successor', {'side_effect': lambda visit, successor, parent: successor})):
            patched = patch('bilqis_mlx.runtime.outcomes.issuance.' + name, **behavior)
            patched.start()
            self.addCleanup(patched.stop)

    def test_priority_hold_never_counts_as_a_neural_visit(self):
        with TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            run_dir.mkdir()
            current = SimpleNamespace(
                generation=4, retained_state=SimpleNamespace(optimizer_step=11))
            progress = []
            with patch(
                    "bilqis_mlx.runtime.bamf_operator.session._visit",
                    return_value="HELD") as visit, patch(
                    "bilqis_mlx.runtime.bamf_operator.session.load_accepted_generation",
                    return_value=current):
                result = operate_bamf(
                    run_dir, minutes=1, max_visits=3, reserve_gib=0.0,
                    progress=progress.append)
        self.assertEqual(result.status, "PRIORITY_HOLD")
        self.assertEqual(result.visits, 0)
        self.assertEqual(result.accepted, 0)
        self.assertEqual(result.rejected, 0)
        self.assertEqual(progress, ["starting visit 1", "visit 1 outcome: HELD"])

    def test_candidate_horizon_rejects_values_above_operator_ceiling(self):
        with self.assertRaises(BilqisError):
            operate_bamf("/run", minutes=1, steps_per_visit=25)

    def test_external_native_run_reaches_source_pool_without_issue_custody(self):
        with TemporaryDirectory() as temporary, patch(
                "bilqis_mlx.runtime.source_prefetch.source_prefetch_pool",
                side_effect=AssertionError("source pool must not start before run custody")) as pool:
            with self.assertRaisesRegex(
                    AssertionError, "source pool must not start before run custody"):
                operate_bamf(
                    temporary, minutes=1, max_visits=1, reserve_gib=0.0)
        pool.assert_called_once()

    def test_no_admissible_priority_selection_never_executes_candidate(self):
        parent = SimpleNamespace()
        context = SimpleNamespace(release=object())
        held = SimpleNamespace(status="NO_ADMISSIBLE_TEACHING", holds=())
        with patch(
                "bilqis_mlx.runtime.bamf_operator.session._execution_context",
                return_value=(parent, context, "atlas", "feature")), patch(
                "bilqis_mlx.runtime.bamf_operator.session.schedule_program_from_executable_release",
                return_value="program"), patch(
                "bilqis_mlx.runtime.bamf_operator.session.accepted_priority_school",
                return_value="school"), patch(
                "bilqis_mlx.runtime.bamf_operator.session.select_foundation_priority_visit",
                return_value=held), patch(
                "bilqis_mlx.runtime.bamf_operator.session._execute_selected_visit",
                side_effect=AssertionError("optimizer candidate must not run")):
            self.assertEqual(_visit("/run", 0.0), "HELD")

    def test_rejection_records_priority_replay_fields_without_advancing_parent(self):
        case = _rejection_routing_fixture()
        result, evidence = _run_rejection_routing_fixture(case)
        self.assertEqual(result, "REJECTED")
        self.assertEqual(evidence["schema"], "bilqis.bamf.c16.3-rejection/v2")
        self.assertEqual(evidence["rejection_journal_ordinal"], 1)
        self.assertEqual(evidence["rejection_attempt_ordinal"], 1)
        self.assertEqual(evidence["visit_id"], "visit:beta")
        self.assertEqual(evidence["selected_option_id"], "capability:beta")
        self.assertEqual(evidence["selected_policy_key"], "policy:beta")
        self.assertEqual(evidence["candidate_optimizer_step"], 12)
        self.assertEqual(evidence["retained_optimizer_step"], 11)
        self.assertEqual(evidence["retention_reason"], "retention_gate")
        self.assertEqual(evidence["candidate_evidence"], _evidence_receipt())
        _assert_rejected_resource(self, evidence["resource"])
        self.assertEqual(case.parent.retained_state.optimizer_step, 11)

    def test_operator_executes_c03_selection_without_reading_factory_release_order(self):
        case = _c03_selection_fixture()
        result, _evidence = _run_rejection_routing_fixture(case)
        self.assertEqual(result, "REJECTED")


if __name__ == "__main__":
    unittest.main()
