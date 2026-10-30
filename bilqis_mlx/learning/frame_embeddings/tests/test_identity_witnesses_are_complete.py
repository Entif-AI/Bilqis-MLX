"""Behavior tests split from their shared fixture owner."""
from dataclasses import replace
import hashlib
from lib.ithkuil.src.skos.publication import json_bytes
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import ConceptBatch, FeatureRequest, SemanticBankView, _local_position, compose_factor_features, embed_atoms, semantic_logits, IndexedLogits, gather_constituents, masked_semantic_loss, plan_identity_initialization, embedding_parameter_view
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.runtime.model_topology import DEFAULT_OPTIMIZER
from bilqis_mlx.semantics.frame_schema import ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan, make_frame_instance
from bilqis_mlx.semantics.context_eligibility import ContextMember, frame_evidence_digest, member_evidence_digest, project_context
from bilqis_mlx.semantics.tests.test_context_eligibility import _case
from bilqis_mlx.semantics.tests.test_atlas_features import _features, _snapshot
from bilqis_mlx.learning.tests.test_frame_embeddings import _context_for, FactorCompositionTests

class FactorCompositionTests2(FactorCompositionTests):
    def test_identity_witnesses_are_complete_and_canonical_under_source_reordering(self):
        weights = mx.zeros((8192, 768), dtype=mx.float32)
        params = {**self.params, "identity.bank.0": weights}
        current = (SemanticBankView(0, weights, (12,), "c"*64, hashlib.sha256(json_bytes([12])).hexdigest()),)
        features = _features(_snapshot(definitions=(("urn:concept:A", ("urn:type:Entity",)),
                                                    ("urn:concept:B", ("urn:type:Entity",)))),
                             schemas=("frame:urn:concept:A", "frame:urn:concept:B"))
        extents = replace(self.extents, active_semantic_digest=hashlib.sha256(json_bytes([11,12])).hexdigest(),
                          factor_map_digest=features.digest)
        first = self.request()
        second = FeatureRequest.from_context(_context_for(self.ref, "fixture:second-source", "frame:urn:concept:B"),
                                              "frame:0", "source:member:right")
        forward = plan_identity_initialization(params, ((first, second, first),), features,
                                                current_banks=current, extents=extents, run_seed=7)[0]
        backward = plan_identity_initialization(params, ((second, first),), features,
                                                 current_banks=current, extents=extents, run_seed=7)[0]
        np.testing.assert_array_equal(forward.weights, backward.weights)
        self.assertEqual(forward.source_witnesses, backward.source_witnesses)
        self.assertEqual(len(forward.source_witnesses), 2)
        self.assertEqual({item.context_digest for item in forward.source_witnesses},
                         {first.projection.digest, second.projection.digest})
        standalone = plan_identity_initialization(params, ((second,),), features,
                                                   current_banks=current, extents=extents, run_seed=7)[0]
        np.testing.assert_array_equal(forward.weights, standalone.weights)

    def test_complete_registry_view_preserves_owned_tensor_objects_and_rejects_other_debt(self):
        spec, extents = ModelTopologySpecV2(), replace(self.extents, semantic_bank_count=2)
        full = {item.name: mx.zeros(item.shape, dtype=mx.float32) for item in expected_bamf_shapes(spec, extents)}
        view = embedding_parameter_view(full, spec=spec, extents=extents)
        names = {"identity.bank.0", "identity.bank.1", "features.type", "features.role", "features.schema",
                 "features.project_type", "features.project_role", "features.project_schema", "features.project_graph",
                 "features.gates", "features.local_slot", "features.norm"}
        self.assertEqual(set(view), names)
        for name in names:
            self.assertIs(view[name], full[name])
        for changed in ({name: value for name, value in full.items() if name != "blocks.11.ffn_in"},
                        {**full, "secret.semantic_head": mx.zeros((768, 768))},
                        {**full, "features.project_role": mx.zeros((128, 768))},
                        {**full, "features.type": full["features.type"].astype(mx.float16)}):
            with self.assertRaises(BilqisError):
                embedding_parameter_view(changed, spec=spec, extents=extents)

    def test_serialized_embedding_prefix_reproduces_tied_logits(self):
        from bilqis_mlx.runtime.disk import assert_headroom
        active_digest = hashlib.sha256(json_bytes([11,12])).hexdigest()
        extents = replace(self.extents, active_semantic_digest=active_digest)
        bank = mx.zeros((8192, 768), dtype=mx.float32).at[11, 0].add(1).at[12, 1].add(2)
        parameters = {**self.params, "identity.bank.0": bank}
        full = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        full.update(parameters)
        parameters = embedding_parameter_view(full, spec=ModelTopologySpecV2(), extents=extents)
        request = self.request()
        def output(params):
            banks = (SemanticBankView(0, params["identity.bank.0"], (11, 12),
                                      self.features.semantic_release, active_digest),)
            hidden = embed_atoms(params, ConceptBatch(((request,),), banks, extents), self.features)
            return semantic_logits(hidden, banks).logits
        expected = output(parameters)
        with TemporaryDirectory() as temporary:
            assert_headroom(Path(temporary), required_bytes=sum(value.size*4 for value in parameters.values()))
            target = Path(temporary)/"disposable-embedding-prefix.safetensors"
            mx.save_safetensors(str(target), parameters)
            restored = mx.load(str(target))
            self.assertEqual(set(restored), set(parameters))
            np.testing.assert_allclose(np.asarray(output(restored)), np.asarray(expected), atol=1e-6, rtol=0)

    def test_disposable_gradient_and_native_adamw_coordinate_coverage(self):
        import mlx.optimizers as optim
        active_digest = hashlib.sha256(json_bytes([11,12])).hexdigest()
        extents = replace(self.extents, active_semantic_digest=active_digest)
        bank = mx.zeros((8192, 768), dtype=mx.float32).at[11, 0].add(1).at[12, 1].add(2)
        parameters = {**self.params, "identity.bank.0": bank}
        request = self.request()
        def objective(params):
            banks = (SemanticBankView(0, params["identity.bank.0"], (11, 12),
                                      self.features.semantic_release, active_digest),)
            hidden = embed_atoms(params, ConceptBatch(((request,),), banks, extents), self.features)
            logits = semantic_logits(hidden, banks)
            return masked_semantic_loss(logits, mx.array([[12]], dtype=mx.uint32),
                                         mx.ones(logits.logits.shape, dtype=mx.bool_))
        gradients = mx.grad(objective)(parameters)
        ledger = {item.name: item for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        report = []
        for name, gradient in gradients.items():
            values = np.asarray(gradient)
            self.assertTrue(np.isfinite(values).all(), name)
            self.assertGreater(float(np.abs(values).sum()), 0, name)
            coordinate = int(np.argmax(np.abs(values)))
            before = parameters[name].reshape(-1)[coordinate:coordinate+1]
            selected_gradient = gradient.reshape(-1)[coordinate:coordinate+1]
            optimizer = optim.AdamW(learning_rate=DEFAULT_OPTIMIZER["learning_rate"],
                                    betas=DEFAULT_OPTIMIZER["betas"], eps=DEFAULT_OPTIMIZER["eps"],
                                    weight_decay=DEFAULT_OPTIMIZER["weight_decay"] if ledger[name].decay else 0,
                                    bias_correction=True)
            after = optimizer.apply_gradients({"coordinate": selected_gradient}, {"coordinate": before})["coordinate"]
            mx.eval(after, optimizer.state)
            self.assertNotEqual(float(after.item()), float(before.item()), name)
            self.assertEqual(float(parameters[name].reshape(-1)[coordinate].item()), float(before.item()))
            report.append({"parameter": name, "shape": list(gradient.shape),
                           "nonzero_gradient_elements": int(np.count_nonzero(values)),
                           "gradient_l1": float(np.abs(values).sum()), "probe_flat_coordinate": coordinate,
                           "before": float(before.item()), "after": float(after.item()),
                           "weight_decay": DEFAULT_OPTIMIZER["weight_decay"] if ledger[name].decay else 0})
        self.assertEqual(len(report), 11)
        if path := os.environ.get("BILQIS_B02_COVERAGE_REPORT"):
            Path(path).write_text(json.dumps({"schema": "bilqis.mlx.embedding-update-coverage/v1",
                                              "scope": "disposable-native-adamw-coordinate-probes",
                                              "whole_model_or_masked_optimizer_qualification": False,
                                              "parameters": sorted(report, key=lambda row: row["parameter"])}, indent=2)+"\n")
