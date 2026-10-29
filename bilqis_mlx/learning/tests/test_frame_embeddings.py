"""Released A06 factor composition feeding B02 and shared depth selection."""
from dataclasses import replace
import hashlib
import json
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import (
    ConceptBatch, FeatureRequest, SemanticBankView, _local_position, compose_factor_features, embed_atoms, semantic_logits,
    IndexedLogits, gather_constituents, masked_semantic_loss, plan_identity_initialization,
)
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan, make_frame_instance,
)
from bilqis_mlx.semantics.context_eligibility import (
    ContextMember, frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.tests.test_context_eligibility import _case
from bilqis_mlx.semantics.tests.test_atlas_features import _features, _snapshot


def _context_for(concept, source_instance="fixture:released-source", schema_id="frame:urn:concept:A"):
    envelopes, task, frontier, policy = _case(count=1, two_roles=True)
    schema = FrameSchema(schema_id, 1, "source:fixture",
                         tuple(RoleSpec(role, concept.type_ids, 1, 1) for role in ("left", "right")),
                         "ORDERED", "source-expression")
    frame = make_frame_instance(schema, source_instance_id=source_instance, structural_path=(),
                                source_span=SourceSpan(0, 8), parent_occurrence_id=None,
                                bindings=tuple(RoleOccurrence(role, 0, concept=concept) for role in ("left", "right")),
                                causal_prefix_end=8)
    members = tuple(ContextMember(role, 0, "source:member:"+role, 8) for role in ("left", "right"))
    envelope = replace(envelopes[0], frame=frame, members=members)
    evidence = {envelope.source_handle: frame_evidence_digest(frame),
                **{member.source_handle: member_evidence_digest(frame, member) for member in members}}
    grants = tuple(replace(frontier.grants[0], source_handle=handle, evidence_digest=digest)
                   for handle, digest in sorted(evidence.items()))
    return project_context((envelope,), task, replace(frontier, grants=grants), policy)


class FactorCompositionTests(unittest.TestCase):
    def setUp(self):
        self.features = _features()
        self.extents = GenerationExtents(1, 1, hashlib.sha256(b"[11]").hexdigest(), "b" * 64, self.features.digest)
        ledger = expected_bamf_shapes(ModelTopologySpecV2(), self.extents)
        self.params = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                       for item in ledger if item.name.startswith("features.")}
        self.params["features.type"] = self.params["features.type"].at[2].add(.5)
        self.params["features.role"] = self.params["features.role"].at[2].add(1).at[3].add(2)
        self.params["features.schema"] = self.params["features.schema"].at[2].add(.25)
        self.params["features.project_type"] = self.params["features.project_type"].at[0, 0].add(2)
        self.params["features.project_role"] = self.params["features.project_role"].at[1, 0].add(3)
        self.params["features.project_schema"] = self.params["features.project_schema"].at[2, 0].add(4)
        self.params["features.project_graph"] = self.params["features.project_graph"].at[3, 4].add(5)
        self.params["features.local_slot"] = self.params["features.local_slot"].at[0, 4].add(7)
        self.params["features.gates"] = mx.full((4,), -2, dtype=mx.float32)
        self.params["features.norm"] = mx.ones((768,), dtype=mx.float32)
        self.ref = ConceptRef("urn:concept:A", self.features.semantic_release, 11,
                              ("urn:type:Entity",), "fixture:qualified-source")

    def request(self, role="left"):
        return FeatureRequest.from_context(_context_for(self.ref), "frame:0", "source:member:"+role)

    def test_source_bound_literal_factor_projection_and_shared_type_role(self):
        result = compose_factor_features(self.params, ((self.request(),),), self.features, extents=self.extents)
        gate = 1 / (1 + np.exp(2))
        expected = np.zeros((1, 1, 768), dtype=np.float32)
        expected[0, 0, :5] = [gate, 3*gate, gate, 5*gate*np.log(2)/np.log(1025), 7]
        np.testing.assert_allclose(np.asarray(result.all_factors), expected, atol=1e-7, rtol=1e-6)
        expected[..., 2:] = 0
        np.testing.assert_allclose(np.asarray(result.type_role), expected, atol=1e-7, rtol=1e-6)
        self.assertEqual(result.feature_digest, self.features.digest)
        self.assertEqual(result.semantic_release, self.features.semantic_release)
        self.assertEqual(result.requests, ((self.request(),),))

    def test_invented_source_coordinates_and_cross_schema_roles_reject(self):
        for field, value in (("role_id", "right"), ("schema_id", "NONE"),
                             ("scope", "invented:scope"), ("local_slot", 1)):
            with self.subTest(field=field), self.assertRaises(BilqisError):
                request = replace(self.request(), **{field: value})
                compose_factor_features(self.params, ((request,),), self.features, extents=self.extents)

    def test_role_is_source_qualified_and_gates_receive_gradients(self):
        left = compose_factor_features(self.params, ((self.request(),),), self.features, extents=self.extents)
        right = compose_factor_features(self.params, ((self.request("right"),),), self.features, extents=self.extents)
        self.assertNotEqual(float(left.type_role[0, 0, 1].item()), float(right.type_role[0, 0, 1].item()))
        def objective(params):
            return mx.sum(compose_factor_features(params, ((self.request(),),), self.features,
                                                  extents=self.extents).all_factors)
        gradients = mx.grad(objective)(self.params)
        self.assertTrue(np.all(np.asarray(gradients["features.gates"]) > 0))
        for name in ("features.type", "features.role", "features.schema", "features.project_type",
                     "features.project_role", "features.project_schema", "features.project_graph"):
            self.assertGreater(float(mx.sum(mx.abs(gradients[name])).item()), 0, name)

    def test_mismatched_source_identity_and_feature_digest_fail_closed(self):
        for changes in ({"concept": replace(self.ref, abi_index=12)},
                        {"concept": replace(self.ref, type_ids=("invented",))},
                        {"role_id": "unreleased"}):
            with self.assertRaises(BilqisError):
                request = replace(self.request(), **changes)
                compose_factor_features(self.params, ((request,),), self.features, extents=self.extents)
        with self.assertRaises(BilqisError):
            compose_factor_features(self.params, ((self.request(),),), self.features,
                                    extents=replace(self.extents, factor_map_digest="f"*64))

    def test_extended_slot_is_deterministic_and_not_a_semantic_abi_index(self):
        # Numeric encoding proof does not invent an admitted 17-member source frame.
        first = _local_position(self.params["features.local_slot"], 16)
        second = _local_position(self.params["features.local_slot"], 16)
        np.testing.assert_array_equal(np.asarray(first), np.asarray(second))
        self.assertAlmostEqual(float(first[4].item()), np.sin(16 / 10000**(4/768)), places=5)
        self.assertEqual(self.request().concept.abi_index, 11)

    def test_embedding_lookup_reuses_active_identity_and_source_factors(self):
        identity = mx.zeros((8192, 768), dtype=mx.float32).at[11, 0].add(1)
        params = {**self.params, "identity.bank.0": identity}
        bank = SemanticBankView(0, identity, (11,), self.features.semantic_release,
                                self.extents.active_semantic_digest)
        batch = ConceptBatch(((self.request(),),), (bank,), self.extents)
        actual = embed_atoms(params, batch, self.features)
        factors = compose_factor_features(params, batch.requests, self.features, extents=self.extents)
        expected = np.asarray(factors.all_factors).copy()
        expected[0, 0, 0] += 1
        expected /= np.sqrt(np.mean(expected*expected, axis=-1, keepdims=True)+1e-5)
        np.testing.assert_allclose(np.asarray(actual), expected, rtol=2e-6, atol=2e-6)
        self.assertIs(bank.weights, params["identity.bank.0"])
        inactive_digest = hashlib.sha256(b"[12]").hexdigest()
        with self.assertRaises(BilqisError):
            embed_atoms(params, replace(batch, banks=(replace(bank, active_rows=(12,),
                                active_semantic_digest=inactive_digest),),
                                extents=replace(self.extents, active_semantic_digest=inactive_digest)), self.features)

    def test_source_type_mean_and_unknown_plus_exact_overflow_vector(self):
        types = tuple(f"urn:type:{index:04d}" for index in range(512))
        features = _features(_snapshot(definitions=(("urn:concept:A", types),)))
        request = FeatureRequest.from_context(_context_for(replace(self.ref, type_ids=types)),
                                              "frame:0", "source:member:left")
        params = {**self.params, "features.type": self.params["features.type"].at[0].add(2)}
        extents = replace(self.extents, factor_map_digest=features.digest)
        actual = compose_factor_features(params, ((request,),), features, extents=extents)
        vectors = []
        for identifier in types:
            index = dict(features.type_map)[identifier]
            vector = np.asarray(params["features.type"])[index].copy()
            if index == 0:
                raw = b"".join(hashlib.sha256(f"bamf.factor.v2|type|{identifier}|{block}".encode()).digest()
                               for block in range(4))
                vector += ((np.frombuffer(raw, dtype=np.uint8)/127.5-1)/np.sqrt(128)).astype(np.float32)
            vectors.append(vector)
        expected_first = np.mean(vectors, axis=0)[0] * 2 / (1+np.exp(2))
        self.assertAlmostEqual(float(actual.type_role[0, 0, 0].item()), float(expected_first), places=7)

    def test_tied_sparse_multibank_readout_uses_global_indices_and_zero_inactive_gradients(self):
        first = mx.zeros((8192, 768), dtype=mx.float32).at[11, 0].add(1).at[14, 0].add(2).at[12, 0].add(1000)
        second = mx.zeros((8192, 768), dtype=mx.float32).at[0, 0].add(3).at[3, 0].add(4)
        hidden = mx.zeros((1, 768), dtype=mx.float32).at[0, 0].add(2)
        active_digest = hashlib.sha256(b"[11,14,8192,8195]").hexdigest()
        def banks(weights):
            return (SemanticBankView(0, weights[0], (11, 14), self.features.semantic_release, active_digest),
                    SemanticBankView(1, weights[1], (0, 3), self.features.semantic_release, active_digest))
        result = semantic_logits(hidden, banks((first, second)))
        self.assertEqual(result.indices, (11, 14, 8192, 8195))
        np.testing.assert_array_equal(np.asarray(result.logits), [[2, 4, 6, 8]])
        self.assertEqual(result.indices[int(mx.argmax(result.logits).item())], 8195)
        gradients = mx.grad(lambda weights: mx.sum(semantic_logits(hidden, banks(weights)).logits))((first, second))
        for gradient, rows in zip(gradients, ((11, 14), (0, 3))):
            expected = np.zeros((8192, 768), dtype=np.float32)
            expected[list(rows), 0] = 2
            np.testing.assert_array_equal(np.asarray(gradient), expected)
        with self.assertRaises(BilqisError):
            semantic_logits(hidden, (replace(banks((first, second))[0], active_rows=()),))

    def test_masked_logsumexp_loss_is_stable_and_illegal_rows_have_zero_gradient(self):
        values = mx.array([[10000, 9999, 50000]], dtype=mx.float32)
        legal = mx.array([[True, True, False]])
        targets = mx.array([8192], dtype=mx.uint32)
        def objective(logits):
            return masked_semantic_loss(IndexedLogits(logits, (11, 8192, 8195)), targets, legal)
        self.assertAlmostEqual(float(objective(values).item()), 1+np.log1p(np.exp(-1)), places=6)
        gradient = mx.grad(objective)(values)
        expected = 1/(1+np.exp(-1))
        np.testing.assert_allclose(np.asarray(gradient), [[expected, -expected, 0]], atol=1e-7)
        for target, mask in ((targets, mx.zeros((1, 3), dtype=mx.bool_)),
                             (mx.array([12]), legal), (mx.array([8195]), legal)):
            with self.assertRaises(BilqisError):
                masked_semantic_loss(IndexedLogits(values, (11, 8192, 8195)), target, mask)
        maximal = IndexedLogits(mx.array([[4]], dtype=mx.float32), (4294967295,))
        self.assertEqual(float(masked_semantic_loss(maximal, mx.array([4294967295], dtype=mx.uint32),
                                                    mx.array([[True]])).item()), 0)
        with self.assertRaises(BilqisError):
            masked_semantic_loss(maximal, mx.array([-1]), mx.array([[True]]))
        with self.assertRaises(BilqisError):
            masked_semantic_loss(IndexedLogits(mx.zeros((0, 3)), (11, 8192, 8195)),
                                  mx.array([], dtype=mx.uint32), mx.zeros((0, 3), dtype=mx.bool_))

    def test_exact_constituent_indices_gather_differentiably_with_padding(self):
        embeddings = mx.arange(2*3*768, dtype=mx.float32).reshape(2, 3, 768)
        indices = mx.array([[[2, 0], [2, 1]], [[1, 0], [0, -1]]])
        valid = mx.array([[[True, True], [True, False]], [[True, True], [True, False]]])
        gathered = gather_constituents(embeddings, indices, valid)
        self.assertEqual(gathered.shape, (2, 2, 2, 768))
        np.testing.assert_array_equal(np.asarray(gathered[0, 0, 0]), np.asarray(embeddings[0, 2]))
        np.testing.assert_array_equal(np.asarray(gathered[1, 1, 1]), np.zeros(768))
        gradients = mx.grad(lambda values: mx.sum(gather_constituents(values, indices, valid)))(embeddings)
        expected = np.array([[1, 0, 2], [2, 1, 0]], dtype=np.float32)
        np.testing.assert_array_equal(np.asarray(gradients), np.broadcast_to(expected[..., None], (2, 3, 768)))
        with self.assertRaises(BilqisError):
            gather_constituents(embeddings, indices, mx.ones(indices.shape, dtype=mx.bool_))

    def test_identity_proposal_is_source_bound_role_invariant_and_preserves_old_rows(self):
        weights = mx.zeros((8192, 768), dtype=mx.float32).at[12, 0].add(9)
        params = {**self.params, "identity.bank.0": weights}
        old_digest = hashlib.sha256(b"[12]").hexdigest()
        current = (SemanticBankView(0, weights, (12,), "c"*64, old_digest),)
        prospective = replace(self.extents, active_semantic_digest=hashlib.sha256(b"[11,12]").hexdigest())
        before = hashlib.sha256(np.asarray(weights).tobytes()).hexdigest()
        left = plan_identity_initialization(params, ((self.request(),),), self.features,
                                             current_banks=current, extents=prospective, run_seed=7)
        right = plan_identity_initialization(params, ((self.request("right"),),), self.features,
                                              current_banks=current, extents=prospective, run_seed=7)
        self.assertEqual(len(left), 1)
        self.assertEqual(left[0].abi_index, 11)
        np.testing.assert_array_equal(left[0].weights, right[0].weights)
        factors = np.zeros(768, dtype=np.float32)
        gate = np.float32(1/(1+np.exp(2)))
        factors[0] = gate
        factors[3] = np.float32(np.log(2)/np.log(1025)) * np.float32(5) * gate
        seed = int.from_bytes(hashlib.sha256(b"bamf.init.v2|7|identity.bank.0|urn:concept:A").digest()[:8], "little")
        expected = (factors.astype(np.float64) + np.random.Generator(np.random.PCG64(seed)).standard_normal(768)*.001).astype(np.float32)
        np.testing.assert_allclose(left[0].weights, expected, atol=1e-8, rtol=1e-6)
        self.assertEqual(hashlib.sha256(np.asarray(weights).tobytes()).hexdigest(), before)
        already_active = (replace(current[0], active_rows=(11,), active_semantic_digest=hashlib.sha256(b"[11]").hexdigest()),)
        with self.assertRaises(BilqisError):
            plan_identity_initialization(params, ((self.request(),),), self.features,
                                          current_banks=already_active, extents=self.extents, run_seed=7)

    def test_identity_witnesses_are_complete_and_canonical_under_source_reordering(self):
        weights = mx.zeros((8192, 768), dtype=mx.float32)
        params = {**self.params, "identity.bank.0": weights}
        current = (SemanticBankView(0, weights, (12,), "c"*64, hashlib.sha256(b"[12]").hexdigest()),)
        features = _features(_snapshot(definitions=(("urn:concept:A", ("urn:type:Entity",)),
                                                    ("urn:concept:B", ("urn:type:Entity",)))),
                             schemas=("frame:urn:concept:A", "frame:urn:concept:B"))
        extents = replace(self.extents, active_semantic_digest=hashlib.sha256(b"[11,12]").hexdigest(),
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


if __name__ == "__main__":
    unittest.main()
