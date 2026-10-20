"""Exercise native bundle/outbox crash windows on temporary toy students only.

This composes existing storage owners; it is not a generic admission executor
and cannot be launched against a saved human run.
"""
from contextlib import redirect_stdout
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx import trainer as storage
from bilqis_mlx.runtime.disk import headroom_snapshot
from bilqis_mlx.runtime.mlx_checkpoint import load_semantically_bound_bundle
from bilqis_mlx.vocabulary_growth import append_catalog, extend_mlx_student
from bilqis_mlx.semantics.tests.test_vocabulary_growth import admission, root_graph, tiny_optimizer


class DisposableCutoverContractTests(unittest.TestCase):
    def setUp(self):
        mx.set_default_device(mx.cpu)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.graph = root_graph()
        self.parameters = {"embedding.weight": mx.array([[.1, .2], [.3, .4], [.5, .6]], dtype=mx.float32),
                           "position.weight": mx.ones((2, 2), dtype=mx.float32)}
        self.optimizer = tiny_optimizer(self.parameters, step=42)
        self.parent = storage._bundle_pointer(self.root, "fixture-parent", self.parameters,
                                              self.optimizer, self.graph, reserve_gib=100)
        self.original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (self.root / self.parent.filename).iterdir()}
        self.receipt = dict(schema="synthetic:cutover-fixture/v1", run_id="fixture-cutover", generation=1,
            source_manifest_sha256="a" * 64, teacher_source_sha256="b" * 64, accepted_authority="synthetic-only",
            school={"current_student": asdict(self.parent), "champions": {}},
            teacher={"observations": ["preserved-fixture-history"]})
        storage._persist(self.root, self.receipt)

    def assert_parent_unchanged(self):
        self.assertEqual(self.original, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in (self.root / self.parent.filename).iterdir()})
        self.assertEqual(int(self.optimizer.state["step"].item()), 42)

    def grown(self):
        graph, _ = append_catalog(self.graph, (admission("fixture.new"),), allow_disposable_fixtures=True)
        parameters, optimizer, _ = extend_mlx_student(self.parameters, self.optimizer, self.graph, graph)
        return parameters, optimizer, graph

    def candidate(self, grow=True):
        parameters, optimizer, graph = self.grown() if grow else (self.parameters, self.optimizer, self.graph)
        pointer = storage._bundle_pointer(self.root, "fixture-candidate", parameters, optimizer, graph,
                                          reserve_gib=100)
        return pointer, parameters, optimizer, graph

    def successor(self, pointer):
        record = {**self.receipt, "generation": 2,
                  "school": {**self.receipt["school"], "current_student": asdict(pointer)}}
        return storage._with_delivery_outbox(record, ({"event": "SCHOOL_DISPOSABLE_CUTOVER",
            "student_sha256": pointer.sha256, "optimizer_step": pointer.optimizer_step,
            "actual_neural_updates": 0},))

    def test_same_vocabulary_and_append_only_growth_preserve_model_and_own_adamw(self):
        for grow in (False, True):
            with self.subTest(grow=grow):
                name = "fixture-same" if not grow else "fixture-grown"
                parameters, optimizer, graph = self.grown() if grow else (self.parameters, self.optimizer, self.graph)
                pointer = storage._bundle_pointer(self.root, name, parameters, optimizer, graph, reserve_gib=100)
                restored, restored_optimizer, _, restored_graph = load_semantically_bound_bundle(self.root / pointer.filename)
                self.assertEqual(restored_graph, graph)
                self.assertEqual(restored_graph["tokens"][:3], self.graph["tokens"])
                self.assertEqual(int(restored_optimizer.state["step"].item()), 42)
                for name, values in self.parameters.items():
                    np.testing.assert_array_equal(np.asarray(restored[name])[:len(values)], np.asarray(values))
                    for moment in ("m", "v"):
                        np.testing.assert_array_equal(np.asarray(restored_optimizer.state[name][moment])[:len(values)],
                                                      np.asarray(self.optimizer.state[name][moment]))
                if grow:
                    self.assertEqual(np.count_nonzero(np.asarray(restored_optimizer.state["embedding.weight"]["m"])[3:]), 0)
                self.assert_parent_unchanged()
        self.assertGreaterEqual(headroom_snapshot(self.root)["reserve_bytes"], 100 * 1024**3)

    def test_disk_stop_and_lost_staging_readback_never_publish_a_candidate(self):
        parameters, optimizer, graph = self.grown()
        with patch("bilqis_mlx.runtime.mlx_checkpoint.assert_headroom", side_effect=RuntimeError("DISK_BUDGET_EXHAUSTED")):
            with self.assertRaisesRegex(RuntimeError, "DISK_BUDGET"):
                storage._bundle_pointer(self.root, "fixture-candidate", parameters, optimizer, graph, reserve_gib=100)
        with patch.object(storage, "load_semantically_bound_bundle", side_effect=RuntimeError("lost readback")):
            with self.assertRaisesRegex(RuntimeError, "lost readback"):
                storage._bundle_pointer(self.root, "fixture-candidate", parameters, optimizer, graph, reserve_gib=100)
        self.assertFalse((self.root / "bundles/fixture-candidate").exists())
        self.assertTrue((self.root / ".bundle-staging/fixture-candidate/model-and-own-adamw.safetensors").exists())
        self.assertEqual(json.loads((self.root / "state.json").read_text()), self.receipt)
        self.assert_parent_unchanged()

    def test_generation_written_before_pointer_is_recovered_without_another_model_allocation(self):
        pointer, _, _, _ = self.candidate()
        record = self.successor(pointer)
        original_write = storage._durable_json
        def fail_pointer(path, value, **kwargs):
            if path.name == "state.json":
                raise RuntimeError("crash before pointer")
            return original_write(path, value, **kwargs)
        with storage.operator_lock(self.root), patch.object(storage, "_durable_json", side_effect=fail_pointer):
            with self.assertRaisesRegex(RuntimeError, "crash before pointer"):
                storage._persist(self.root, record)
        self.assertEqual(json.loads((self.root / "state.json").read_text())["generation"], 1)
        with redirect_stdout(io.StringIO()), storage.operator_lock(self.root), \
                patch.object(storage, "_bundle_pointer", side_effect=AssertionError("duplicate allocation")):
            recovered = storage._recover_orphaned_commit(self.root, self.receipt)
            storage._reconcile_delivery_outbox(self.root, recovered)
        self.assertEqual(recovered["generation"], 2)
        self.assertEqual(recovered["teacher"], self.receipt["teacher"])
        self.assert_parent_unchanged()

    def test_lost_event_ack_replays_only_missing_ids_and_rejects_payload_forgery(self):
        pointer, _, _, _ = self.candidate()
        record = self.successor(pointer)
        storage._persist(self.root, record)
        append = storage._record
        def lost_ack(run_dir, event):
            append(run_dir, event)
            raise RuntimeError("lost event acknowledgement")
        with redirect_stdout(io.StringIO()), storage.operator_lock(self.root):
            with patch.object(storage, "_record", side_effect=lost_ack), self.assertRaises(RuntimeError):
                storage._reconcile_delivery_outbox(self.root, record)
            storage._reconcile_delivery_outbox(self.root, record)
            storage._reconcile_delivery_outbox(self.root, record)
        events = [json.loads(line) for line in (self.root / "events.jsonl").read_text().splitlines()]
        self.assertEqual(len(events), 1)
        events[0]["optimizer_step"] = 99
        (self.root / "events.jsonl").write_text(json.dumps(events[0]) + "\n")
        with storage.operator_lock(self.root), self.assertRaisesRegex(ValueError, "LEDGER_CONTENT_DRIFT"):
            storage._reconcile_delivery_outbox(self.root, record)
        self.assert_parent_unchanged()
