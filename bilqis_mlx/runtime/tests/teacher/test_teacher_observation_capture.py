"""Observation storage is replayable and has no authority over learner behavior."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.teacher_observation_capture import store_sidecar, read_sidecar


class ObservationSidecarTests(unittest.TestCase):
    def test_content_addressing_is_idempotent_and_preserves_order(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"rows": [{"id": "one"}, {"id": "one"}, {"id": "two"}]}
            reference = store_sidecar(root, payload)
            self.assertEqual(store_sidecar(root, payload), reference)
            self.assertEqual(read_sidecar(root, reference), payload)
            self.assertNotEqual(store_sidecar(root, {"rows": list(reversed(payload["rows"]))}), reference)
            path = root / reference["file"]
            path.write_text(json.dumps({"rows": []}))
            with self.assertRaises(ValueError):
                read_sidecar(root, reference)


class VisitObservationTests(unittest.TestCase):
    def _install_seams(self, patches, visits, release, program, fixture, draw, evidence, predictions, train):
        patches.enter_context(patch.object(visits._runtime_admission, "_read_executable_factory_release_artifact", return_value=release))
        patches.enter_context(patch.object(visits._runtime_release_adoption, "_schedule_for_receipt", return_value=program))
        patches.enter_context(patch.object(visits._runtime_assessment, "_draw_live_rows", side_effect=draw))
        patches.enter_context(patch.object(visits._source_adapters_school, "live_source_registry", return_value=fixture.registry))
        patches.enter_context(patch.object(visits._runtime_candidate_evidence, "_candidate_grade_evidence", side_effect=evidence))
        patches.enter_context(patch.object(visits._learning_student_ops, "_predictions", side_effect=predictions))
        patches.enter_context(patch.object(visits._learning_student_ops, "_train_step", side_effect=train))
        patches.enter_context(patch.object(visits, "_visit_retention_scope", return_value=(("Z.C1",), ("Z.C1",))))
        patches.enter_context(patch("bilqis_mlx.learning.matrix_strain.observe", return_value={"status": "NOT_MEASURED"}))

    def _fixture(self, previous):
        import mlx.core as mx
        from copy import deepcopy
        from dataclasses import asdict, replace
        from bilqis_mlx.factory.tests.test_executable_release import ExecutableFactoryReleaseTests
        from bilqis_mlx.factory.adapters import SourceAdapterRegistry
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.learning.champions import Checkpoint
        from bilqis_mlx.runtime import state
        from bilqis_mlx.runtime.model_topology import ModelTopologySpec, create_student
        fixture = ExecutableFactoryReleaseTests()
        fixture.setUp()
        adapter = next(iter(fixture.registry.adapters.values())) if hasattr(fixture.registry, "adapters") else fixture.registry.require("fixture.z-generator/v1", "fixture.z-oracle/v1")
        def source_rows(**kwargs):
            return tuple({**row, "tokens": [1 if row["gold"] == "FALSE" else 2],
                          "record": {"source": row["id"]}}
                         for row in adapter.draw(**kwargs))
        fixture.registry = SourceAdapterRegistry((replace(adapter, draw=source_rows),))
        from bilqis_mlx.vocabulary_growth import digest
        nodes = [dict(id=token, meaning=token, semantic_id="fixture:" + token, family="logic",
                      subtype="atomic", signature="SemanticSymbol", arity=0,
                      source="fixture:observations", admission_receipt="a" * 64)
                 for token in fixture.graph["tokens"]]
        fixture.graph.update(nodes=nodes, row_contract_sha256={node["id"]: digest(node) for node in nodes})
        release = fixture.compile()
        program = schedule_program_from_executable_release(release)
        pointer = Checkpoint("a" * 64, "bundles/fixture", 0, True)
        topology = ModelTopologySpec(1, 2, 12, 24, 96)
        parameters, optimizer = create_student(topology, len(fixture.graph["tokens"]), seed=5)
        receipt = previous or dict(generation=1, run_id="same-disposable-run", teacher={"strategies": {}},
            school=asdict(start_new(program, pointer)), config=dict(layers=1, heads=2, width=12,
                ffn_dimension=24, context=96, precision="fp32", vocab_size=3),
            model_topology=topology.to_record(), model_initialization={"origin": "fresh-model", "seed": 5},
            model_implementation={"provider": "mlx"}, source_manifest_sha256="b" * 64,
            teacher_source_sha256="c" * 64, semantic_graph_sha256=state._fingerprint(fixture.graph),
            factory_release_sha256=release.release_sha256, answer_ids=[1, 2], curriculum_mode="fixture")
        receipt = deepcopy(receipt)
        policy = dict(old=1, preview=0, depth=1, contrast=1., lr=.00013, distill=0.)
        receipt["teacher"]["strategies"] = {"fixture-policy": policy}
        return fixture, release, program, parameters, optimizer, receipt, policy

    def run_visit(self, *, enabled=True, outcome_kind="retained", autonomy=False,
                  previous=None, use_schedule_program=False):
        try:
            import mlx.core as mx
            import numpy as np
        except ImportError:
            self.skipTest("native MLX unavailable")
        from contextlib import ExitStack
        from types import SimpleNamespace
        from bilqis_mlx.factory.generation import draw_executable_release_rows
        from bilqis_mlx.learning.learning_experiment import Settings
        from bilqis_mlx.runtime import visits, state
        from bilqis_mlx.runtime.teacher_observation_capture import read_observation
        fixture, release, program, parameters, optimizer, receipt, policy = self._fixture(previous)
        trace = {"pick": [], "observe": [], "draw": [], "train": []}
        def pick(teacher, grade, rng):
            trace["pick"].append((grade, rng.getstate(), rng.random(), rng.getstate()))
            return "fixture-policy", policy
        def observe(teacher, grade, key, reward):
            trace["observe"].append((grade, key, reward))
            teacher["events"] = teacher.get("events", 0) + 1
        engine = SimpleNamespace(pick=pick, observe=observe)
        def draw(root, graph, *, seed, capability, each, **kwargs):
            result = list(draw_executable_release_rows(root, graph, release, fixture.registry,
                seed=seed, capability=capability, each=each))
            trace["draw"].append((seed, capability, each, [row["id"] for row in result]))
            return result
        def predictions(_mx, weights, selected, *_):
            return {row["id"]: (row["gold"] if outcome_kind == "skip" else "FALSE") for row in selected}
        target = "Z.C0"
        def evidence(*args):
            pair = {cap.id: {"before": 1, "after": 1, "total": 6} for cap in program.grades[0].capabilities}
            pair[target]["after"] = 2 if outcome_kind != "target-only" else 1
            if outcome_kind == "rejected":
                pair["Z.C1"]["before"], pair["Z.C1"]["after"] = 6, 0
            if outcome_kind == "target-only":
                pair = {target: pair[target]}
                protected, required, stage = set(), (target,), "TARGET_ONLY_REJECTED"
            else:
                protected, required, stage = set(pair) - {target}, tuple(pair), "COMPLETE_SAME_GRADE"
            missing = {"status": "NOT_MEASURED", "reason": "FIXTURE_NO_FRONTIER"}
            return pair, protected, required, missing, missing, missing, stage
        original_train = visits._learning_student_ops._train_step
        def train(mx, weights, own_adamw, rows, *args, **kwargs):
            trace["train"].append(([row["id"] for row in rows], int(own_adamw.state["step"].item())))
            return original_train(mx, weights, own_adamw, rows, *args, **kwargs)
        with TemporaryDirectory() as tmp, ExitStack() as patches:
            root = Path(tmp)
            self._install_seams(patches, visits, release, program, fixture, draw, evidence, predictions, train)
            mx.set_default_device(mx.cpu)
            result = visits._take_visit(mx, root, receipt, {"manifest_sha256": "b" * 64},
                program if use_schedule_program else fixture.course,
                engine, parameters, optimizer, fixture.graph, steps_per_visit=2,
                batch_size=6, reserve_gib=0., source_root=root, learning_settings=Settings(),
                autonomy_teaching_option="source.direct/Z.C0" if autonomy else None,
                capture_teacher_observations=enabled)
            from bilqis_mlx.runtime.checkpoints import _bundle_pointer
            from bilqis_mlx.runtime.model_topology import ModelTopologySpec
            published = _bundle_pointer(root, "observed-result", parameters, optimizer, fixture.graph,
                reserve_gib=0., model_topology=ModelTopologySpec.from_record(receipt["model_topology"]))
            event = result["_pending_visit_events"][-1]
            observation = read_observation(root, event) if enabled else None
            if enabled:
                self._assert_cold_publication(root, result, published, outcome_kind, observation)
            learner = {key: np.asarray(value).tolist() for key, value in parameters.items()}
            adamw = {key: ({name: np.asarray(value).tolist() for name, value in cell.items()}
                           if isinstance(cell, dict) else np.asarray(cell).tolist())
                     for key, cell in optimizer.state.items()}
            return dict(trace=trace, result=result, learner=learner, adamw=adamw,
                        observation=observation, event=event, release=release.release_sha256, published=published)

    def test_schedule_projection_visit_uses_release_curriculum_for_methodology(self):
        try:
            import mlx.core  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("native MLX unavailable")
        from bilqis_mlx.factory.curriculum_definition import CurriculumDefinition
        from bilqis_mlx.runtime import visits
        seen = []
        summarize = visits._diagnostics_teaching.summarize_teaching_visit

        def capture_authority(course, *args, **kwargs):
            seen.append(course)
            return summarize(course, *args, **kwargs)

        with patch.object(visits._diagnostics_teaching, "summarize_teaching_visit",
                          side_effect=capture_authority):
            result = self.run_visit(use_schedule_program=True)
        methodology = result["event"]["lesson_methodology"]
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], CurriculumDefinition)
        self.assertEqual(methodology["capability"], "Z.C0")
        self.assertTrue(methodology["course_sha256"])

    def _assert_cold_publication(self, root, result, published, outcome_kind, observation):
        from contextlib import redirect_stdout
        from dataclasses import asdict
        import io
        from bilqis_mlx.runtime import checkpoints
        from bilqis_mlx.runtime.teacher_observation_replay import read_committed_observations
        from bilqis_mlx.learning.teacher_observations import summarize_observations
        committed = {**result, "school": {**result["school"], "current_student": asdict(published)}}
        pending = committed.pop("_pending_visit_events")
        boundary = checkpoints._boundary_delivery_events(committed, pending, (), None)
        committed = checkpoints._persist(root, checkpoints._with_delivery_outbox(committed, boundary))
        cold = read_committed_observations(root)
        self.assertEqual(len(cold), 1)
        self.assertEqual(cold[0]["ledger_delivery"], "OUTBOX_COMMITTED_NOT_EMITTED")
        with redirect_stdout(io.StringIO()):
            checkpoints._reconcile_delivery_outbox(root, committed)
            journal = (root / "events.jsonl").read_bytes()
            checkpoints._reconcile_delivery_outbox(root, committed)
        self.assertEqual((root / "events.jsonl").read_bytes(), journal)
        emitted = read_committed_observations(root)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["event_id"], cold[0]["event_id"])
        self.assertEqual(emitted[0]["publication"]["checkpoint"], asdict(published))
        summary = summarize_observations(emitted)
        self.assertEqual(summary["attempted_steps"]["value"], 0 if outcome_kind == "skip" else 2)
        expected = ("NOT_MEASURED" if outcome_kind == "skip" else "MEASURED")
        self.assertEqual(observation["outcome"]["retention"]["status"], expected)
        if outcome_kind == "skip":
            self.assertEqual(observation["outcome"]["target"]["before"]["status"], "MEASURED")
            self.assertFalse(observation["steps"])
        else:
            self.assertEqual(observation["outcome"]["retention"]["value"],
                             "RETAINED" if outcome_kind == "retained" else "REJECTED")
        if outcome_kind == "target-only":
            self.assertEqual(observation["outcome"]["protected"]["net_correct_delta"]["status"], "NOT_MEASURED")

    def test_enabled_disabled_orchestration_is_behaviorally_identical(self):
        from copy import deepcopy
        for kind, autonomy in ((kind, autonomy) for kind in ("retained", "rejected", "target-only", "skip") for autonomy in (False, True)):
            with self.subTest(kind=kind, autonomy=autonomy):
                enabled = self.run_visit(enabled=True, outcome_kind=kind, autonomy=autonomy)
                disabled = self.run_visit(enabled=False, outcome_kind=kind, autonomy=autonomy)
                self.assertEqual(enabled["trace"], disabled["trace"])
                self.assertEqual(enabled["learner"], disabled["learner"])
                self.assertEqual(enabled["adamw"], disabled["adamw"])
                self.assertEqual(enabled["release"], disabled["release"])
                self.assertEqual(enabled["published"], disabled["published"])
                without_evidence = deepcopy(enabled["result"])
                for event in without_evidence["_pending_visit_events"]:
                    event.pop("teacher_observation", None)
                self.assertEqual(without_evidence, disabled["result"])

    def test_ordinary_and_autonomy_capture_actual_support_and_order(self):
        for autonomy in (False, True):
            with self.subTest(autonomy=autonomy):
                result = self.run_visit(autonomy=autonomy)
                observation = result["observation"]
                self.assertEqual(len(observation["steps"]), 2)
                for step, trained in zip(observation["steps"], result["trace"]["train"]):
                    self.assertEqual([position["row"]["id"] for position in step["positions"]], trained[0])
                    self.assertTrue(any("retention_support" in position["roles"] for position in step["positions"]))
                    self.assertIsNotNone(step["delivered_teaching"])
                    self.assertTrue(step["realization_changed"])


class CaptureIdentityTests(unittest.TestCase):
    def capture(self, root, *, topology_width=12, stats=0, steps=2):
        from copy import deepcopy
        from dataclasses import asdict
        from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
        from bilqis_mlx.factory.tests.test_executable_release import ExecutableFactoryReleaseTests
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.learning.champions import Checkpoint
        from bilqis_mlx.runtime.model_topology import ModelTopologySpec
        fixture = ExecutableFactoryReleaseTests()
        fixture.setUp()
        release = fixture.compile()
        school = start_new(schedule_program_from_executable_release(release), Checkpoint("a" * 64, "bundles/fixture", 0, True))
        receipt = dict(run_id="fixture", generation=1, school=asdict(school),
            model_topology=ModelTopologySpec(1, 2, topology_width, 24, 96).to_record(), teacher_source_sha256="c" * 64)
        teacher = {"strategies": {"fixed": {"lr": .00013}}, "events": stats}
        capture = ObservationCapture(root, receipt)
        capture.select_option("Z.C0", None)
        capture.propose(release, school, "Z.C0", "fixed", teacher["strategies"]["fixed"], {},
            configured_steps=steps, effective_steps=steps, batch_size=6, settings=None,
            enrichment=False, source_rows=[], teacher=teacher, parent_optimizer_step=0)
        return capture, release

    def test_topology_is_partition_and_statistics_do_not_change_policy_epoch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, _ = self.capture(root)
            stats, _ = self.capture(root, stats=50)
            topology, _ = self.capture(root, topology_width=24)
            epoch, _ = self.capture(root, steps=4)
            self.assertEqual(first.proposal["policy_evidence_epoch"], stats.proposal["policy_evidence_epoch"])
            self.assertEqual(first.proposal["policy_evidence_epoch"], topology.proposal["policy_evidence_epoch"])
            self.assertNotEqual(first.proposal["partition"], topology.proposal["partition"])
            self.assertEqual(first.proposal["student_region"], topology.proposal["student_region"])
            self.assertNotEqual(first.proposal["policy_evidence_epoch"], epoch.proposal["policy_evidence_epoch"])

    def test_realized_step_preserves_multiplicity_and_changed_composition(self):
        from bilqis_mlx.runtime.teacher_observation_capture import read_sidecar
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture, release = self.capture(root)
            one = dict(id="one", capability="Z.C0", gold="FALSE")
            support = dict(id="support", capability="Z.C1", gold="TRUE")
            capture.delivery(release, "Z.C0", 1, [one, one, support], option_rows=[one],
                priority=(), preservation=(), support=[support], enrichment=(), guidance=None,
                controls={"old": 1}, seed=17)
            step = read_sidecar(root, capture.steps[0])
            self.assertEqual([position["row"]["sha256"] for position in step["positions"]][:2],
                             [step["positions"][0]["row"]["sha256"]] * 2)
            self.assertEqual(step["delivered_teaching"]["specimen_ids"], ["one"])
            self.assertEqual(len(step["positions"]), 3)
            self.assertEqual(step["positions"][-1]["roles"], ["retention_support"])
            self.assertTrue(step["realization_changed"])


    def test_readback_verifies_policy_and_selection_context_objects(self):
        from bilqis_mlx.runtime.teacher_observation_capture import read_observation
        for field in ("policy_evidence_epoch", "selection_source_context"):
            with self.subTest(field=field), TemporaryDirectory() as tmp:
                root = Path(tmp)
                capture, _ = self.capture(root)
                event = {}
                capture.finish(event, decision=None, paired=None, protected=None,
                    stage="ORDINARY", attempted=1, retained=1)
                (root / capture.proposal[field]["file"]).write_text("{}")
                with self.assertRaisesRegex(ValueError, "CONTENT_MISMATCH"):
                    read_observation(root, event)

    def test_skip_scores_preserve_only_valid_pre_action_measurements(self):
        from bilqis_mlx.runtime.teacher_observation_capture import read_observation
        for correct, total, expected in ((6, 6, "MEASURED"), (0, 0, "NOT_MEASURED"),
                                          (7, 6, "NOT_MEASURED")):
            with self.subTest(correct=correct, total=total), TemporaryDirectory() as tmp:
                root = Path(tmp)
                capture, _ = self.capture(root)
                event = {"target_probe_correct": correct, "target_probe_total": total}
                capture.finish(event, decision=None, paired=None, protected=None,
                    stage="PERFECT_TARGET_SKIP", attempted=0, retained=0)
                observation = read_observation(root, event)
                self.assertEqual(observation["outcome"]["target"]["before"]["status"], expected)
                self.assertEqual(observation["outcome"]["target"]["after"]["status"], "NOT_MEASURED")
                self.assertEqual(observation["attempt_status"], "SELECTION_SKIPPED")
