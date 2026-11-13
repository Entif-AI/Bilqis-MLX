"""Run topology rejects drift before recovery or checkpoint publication."""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.model_topology import ModelTopologySpec
from bilqis_mlx.runtime.topology_lifecycle import inspect_resume_topology, topology_from_file


def _synthetic_release():
    from bilqis_mlx.factory.tests.test_executable_release import ExecutableFactoryReleaseTests
    from bilqis_mlx.vocabulary_growth import digest
    fixture = ExecutableFactoryReleaseTests()
    fixture.setUp()
    tokens = [*fixture.graph["tokens"], "micro.state.UNKNOWN", "micro.state.CONFLICT", "micro.state.AMBIGUOUS"]
    nodes = [dict(id=token, semantic_id="fixture:" + token, meaning=token,
        family="logic", subtype="atomic", signature="SemanticSymbol", arity=0,
        source="fixture:topology", admission_receipt="a" * 64) for token in tokens]
    fixture.graph = dict(tokens=tokens, nodes=nodes,
        row_contract_sha256={node["id"]: digest(node) for node in nodes})
    return fixture, fixture.compile()


class TopologyLifecycleTests(unittest.TestCase):
    def test_mismatched_request_fails_before_checkpoint_recovery(self):
        from bilqis_mlx.runtime import session
        saved = {"factory_admission_v2": {}, "config": {
            "layers": 2, "heads": 2, "width": 12, "expansion": 4, "context": 96}}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state.json").write_text("{}")
            with patch.object(session._state_dag, "read_current", return_value=saved), \
                    patch.object(session._runtime_checkpoints, "_clean_staged_bundles") as clean:
                with self.assertRaises(ValueError):
                    session._resume(root, {}, None, None, grade_a_course=None,
                        source_root=None, model_topology=ModelTopologySpec(3, 2, 12, 48, 96))
                clean.assert_not_called()

    def test_historical_config_resolves_without_writing_metadata(self):
        config = {"layers": 2, "heads": 2, "width": 12, "expansion": 4, "context": 96}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = {"config": config, "model_bundle": "bundles/historical"}
            bundle = root / saved["model_bundle"]
            bundle.mkdir(parents=True)
            manifest = bundle / "manifest.json"
            manifest.write_text(json.dumps({"schema": "historical"}))
            before = manifest.read_bytes()
            topology = inspect_resume_topology(root, saved)
            self.assertEqual(topology.width, 12)
            self.assertEqual(topology.ffn_dimension, 48)
            self.assertEqual(manifest.read_bytes(), before)
            self.assertNotIn("model_topology", saved)

    def test_cli_file_uses_canonical_versioned_record(self):
        topology = ModelTopologySpec(1, 2, 12, 19, 128)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "topology.json"
            path.write_text(json.dumps(topology.to_record()))
            self.assertEqual(topology_from_file(path), topology)
            path.write_text('{"layers": 1}')
            with self.assertRaises(ValueError):
                topology_from_file(path)

    def test_same_run_creation_and_durable_cold_resume(self):
        try:
            import mlx.core as mx
        except ImportError:
            self.skipTest("MLX unavailable")
        import numpy as np
        import torch
        from bilqis_mlx.runtime import session, topology_lifecycle as lifecycle
        from bilqis_mlx.runtime.model_topology import CURRENT_DEFAULT_TOPOLOGY, create_student
        from bilqis_mlx.runtime.mlx_checkpoint import load_semantically_bound_bundle
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.runtime.mlx_parity import forward
        from bilqis_mlx.state_dag import read_current
        fixture, release = _synthetic_release()
        choices = {"default": CURRENT_DEFAULT_TOPOLOGY,
                   "small-a": ModelTopologySpec(1, 2, 12, 19, 128),
                   "small-b": ModelTopologySpec(2, 4, 20, 41, 48)}
        inherited = CURRENT_DEFAULT_TOPOLOGY
        config = dict(layers=inherited.layers, heads=inherited.heads, width=inherited.width,
            expansion=4, context=inherited.context, precision="fp32", vocab_size=len(fixture.graph["tokens"]))
        optimizer_config = dict(lr=0.00013, betas=[.9, .95], eps=1e-8, weight_decay=.01)
        payload = dict(config=config, graph=fixture.graph, optimizer={"param_groups": [optimizer_config]})
        program = schedule_program_from_executable_release(release)
        manifest = dict(manifest_sha256="a" * 64, exam_rubric_sha256="b" * 64)
        mx.set_default_device(mx.cpu)
        for choice, topology in choices.items():
            with self.subTest(choice=choice), TemporaryDirectory() as tmp, ExitStack() as stack:
                root = Path(tmp)
                run = root / "run"
                run.mkdir()
                def imported(_):
                    parameters, optimizer = create_student(inherited, len(fixture.graph["tokens"]),
                                                           seed=17, optimizer_config=optimizer_config)
                    return parameters, optimizer, config, fixture.graph, [1, 2, 3, 4, 5]
                stack.enter_context(patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}))
                stack.enter_context(patch.object(torch, "load", return_value=payload))
                stack.enter_context(patch("bilqis_mlx.learning.student_ops._initial_model", side_effect=imported))
                stack.enter_context(patch.object(session._compatibility_executable_projection,
                    "compile_projected_executable_release", return_value=(release, program, None)))
                parameters, optimizer, graph, receipt = session._init(run, manifest, fixture.course,
                    "c" * 64, {}, {}, Path("unused-source"), source_root=None, reserve_gib=0.,
                    model_topology=None if choice == "default" else topology)
                self.assertEqual(receipt["model_topology"], topology.to_record())
                self.assertEqual(receipt["factory_release_sha256"], release.release_sha256)
                self.assertEqual(receipt["model_implementation"]["provider"], "mlx")
                disk = read_current(run)
                restored, own_adamw, bundle, restored_graph = load_semantically_bound_bundle(run / disk["model_bundle"])
                self.assertEqual(inspect_resume_topology(run, disk), topology)
                self.assertEqual(bundle["model_topology"], topology.to_record())
                self.assertEqual(int(own_adamw.state["step"].item()), 0)
                self.assertEqual(restored_graph, graph)
                ids = np.asarray([[1, 2]], dtype=np.int32)
                before = forward(mx, parameters, ids, [2], heads=topology.heads,
                                 layers=topology.layers, answer_ids=[1, 2])
                after = forward(mx, restored, ids, [2], heads=disk["config"]["heads"],
                                layers=disk["config"]["layers"], answer_ids=[1, 2])
                np.testing.assert_array_equal(before, after)
                with patch.object(lifecycle, "initial_model", side_effect=AssertionError("reinitialized")), \
                        patch("bilqis_mlx.runtime.model_topology.CURRENT_DEFAULT_TOPOLOGY", None):
                    self.assertEqual(inspect_resume_topology(run, read_current(run)), topology)
                    resumed_parameters, resumed_adamw, resumed_graph, resumed_receipt = session._resume(
                        run, manifest, fixture.course, "c" * 64, grade_a_course=fixture.course,
                        source_root=None, model_topology=topology)
                    self.assertEqual(resumed_receipt["model_topology"], topology.to_record())
                    self.assertEqual(resumed_graph, graph)
                    np.testing.assert_array_equal(np.asarray(resumed_parameters["embedding.weight"]),
                                                  np.asarray(restored["embedding.weight"]))
                with self.assertRaises(ValueError):
                    inspect_resume_topology(run, disk, ModelTopologySpec(3, 2, 12, 48, 96))
                self.assertEqual(read_current(run), disk)

    def test_append_only_growth_keeps_topology_and_existing_predictions(self):
        try:
            import mlx.core as mx
        except ImportError:
            self.skipTest("MLX unavailable")
        import numpy as np
        from bilqis_mlx.runtime.model_topology import create_student, validate_parameter_shapes
        from bilqis_mlx.runtime.mlx_parity import forward
        from bilqis_mlx.vocabulary_growth import extend_mlx_student, digest
        fixture, _ = _synthetic_release()
        prior = fixture.graph
        extra = dict(id="fixture.new", semantic_id="fixture:new", meaning="fixture new",
            family="logic", subtype="atomic", signature="SemanticSymbol", arity=0,
            source="fixture:topology", admission_receipt="b" * 64)
        expanded = dict(tokens=[*prior["tokens"], extra["id"]], nodes=[*prior["nodes"], extra],
            row_contract_sha256={**prior["row_contract_sha256"], extra["id"]: digest(extra)})
        topology = ModelTopologySpec(2, 4, 20, 41, 48)
        parameters, optimizer = create_student(topology, len(prior["tokens"]), seed=3)
        grown, own_adamw, receipt = extend_mlx_student(parameters, optimizer, prior, expanded)
        validate_parameter_shapes(grown, topology, len(expanded["tokens"]))
        self.assertEqual(receipt["train_updates"], 0)
        for name in parameters:
            old = np.asarray(parameters[name])
            new = np.asarray(grown[name])
            np.testing.assert_array_equal(old, new[:len(old)] if name == "embedding.weight" else new)
        ids = np.asarray([[1, 2]], dtype=np.int32)
        def predict(weights):
            return forward(mx, weights, ids, [2], heads=topology.heads,
                           layers=topology.layers, answer_ids=[1, 2])
        np.testing.assert_array_equal(predict(parameters), predict(grown))
        self.assertEqual(int(own_adamw.state["step"].item()), int(optimizer.state["step"].item()))
        self.assertEqual(int(optimizer.state["step"].item()), 0)

    def test_cli_declares_single_topology_file_surface(self):
        from bilqis_mlx.cli import parse_args
        args = parse_args(["train", "--dry-run", "--model-topology", "topology.json"])
        self.assertEqual(args.model_topology, Path("topology.json"))
        with TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.json"
            broken.write_text("{")
            with self.assertRaisesRegex(ValueError, "MODEL_TOPOLOGY.RECORD_INVALID"):
                topology_from_file(broken)

    def test_checkpoint_head_identity_drift_rejected_before_recovery(self):
        topology = ModelTopologySpec(2, 2, 12, 48, 96)
        other_heads = ModelTopologySpec(2, 3, 12, 48, 96)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundles" / "fixture"
            bundle.mkdir(parents=True)
            manifest = bundle / "manifest.json"
            manifest.write_text(json.dumps({"model_topology": other_heads.to_record()}))
            config = dict(layers=2, heads=2, width=12, expansion=4, context=96)
            receipt = dict(config=config, model_topology=topology.to_record(), model_bundle="bundles/fixture")
            before = manifest.read_bytes()
            with self.assertRaisesRegex(ValueError, "MODEL_TOPOLOGY.MISMATCH"):
                inspect_resume_topology(root, receipt)
            self.assertEqual(manifest.read_bytes(), before)

    def test_context_uses_topology_extent_before_forward(self):
        try:
            import mlx.core as mx
        except ImportError:
            self.skipTest("MLX unavailable")
        from bilqis_mlx.learning import student_ops
        from bilqis_mlx.runtime.model_topology import create_student
        mx.set_default_device(mx.cpu)
        topology = ModelTopologySpec(1, 2, 12, 19, 128)
        parameters, _ = create_student(topology, 128, seed=5)
        config = {"heads": topology.heads, "layers": topology.layers}
        rows = [{"id": "long", "tokens": list(range(100)), "gold": "TRUE"}]
        with patch.object(student_ops._runtime_mlx_parity, "forward_arrays", return_value=mx.zeros((1, 2))) as forward:
            self.assertEqual(student_ops._predictions(mx, parameters, rows, config, [1, 2]), {"long": "FALSE"})
            forward.assert_called_once()
        restricted = ModelTopologySpec(1, 2, 12, 19, 48)
        limited, _ = create_student(restricted, 128, seed=6)
        too_long = [{"id": "long", "tokens": list(range(49)), "gold": "TRUE"}]
        with patch.object(student_ops._runtime_mlx_parity, "forward_arrays") as forward:
            with self.assertRaisesRegex(ValueError, "SEQUENCE_OUTSIDE_LEGACY_CONTEXT"):
                student_ops._predictions(mx, limited, too_long, config, [1, 2])
            forward.assert_not_called()


if __name__ == "__main__":
    unittest.main()
