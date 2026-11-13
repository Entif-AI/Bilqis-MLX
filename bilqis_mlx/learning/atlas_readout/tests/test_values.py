"""Native labels retain their existing tied semantic ABI."""
from dataclasses import replace
import unittest
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.learning.atlas_readout.values import bind_value_head, value_logits
from bilqis_mlx.learning.atlas_readout.tests.helpers import snapshot, banks


class ValueHeadTests(unittest.TestCase):
    def setUp(self):
        mx.set_default_device(mx.cpu)
        self.source = snapshot()
        self.banks = banks(self.source)
        self.registry = live_answer_registry()
        self.hidden = mx.zeros((768,)).at[0].add(1)

    def bind(self, kind='binary', values=('FALSE', 'TRUE')):
        return bind_value_head(kind, values, self.source, self.registry)

    def test_existing_binary_and_numeric_bindings(self):
        binary = self.bind()
        number = self.bind('numeric_active', ('0', '1'))
        self.assertEqual(binary.abi_indices, (11, 12))
        self.assertEqual(binary.modality_id, 'answer.binary/v1')
        self.assertEqual(number.abi_indices, (13, 14))
        self.assertEqual(value_logits(self.hidden, binary, self.banks).logits.tolist(), [11., 12.])
        with self.assertRaises(ValueError):
            self.bind('binary', ('TRUE', 'FALSE'))

    def test_sparse_bank1_predicts_exact_global_identity(self):
        binding = self.bind('semantic_token', ('bank1', 'cogal.value.true'))
        output = value_logits(self.hidden, binding, self.banks)
        self.assertEqual(output.candidates, ('bank1', 'cogal.value.true'))
        self.assertEqual(output.logits.tolist(), [2., 12.])
        self.assertEqual(binding.abi_indices, (8193, 12))

    def test_inactive_missing_and_duplicate_values_reject(self):
        for values in [('inactive',), ('missing',), ('bank1', 'bank1'), ()]:
            with self.subTest(values=values), self.assertRaises(BilqisError):
                self.bind('semantic_token', values)

    def test_foreign_release_or_active_set_rejects(self):
        binding = self.bind()
        for field in ('semantic_release', 'active_semantic_digest'):
            changed = tuple(replace(b, **{field: 'e'*64}) for b in self.banks)
            with self.subTest(field=field), self.assertRaises(BilqisError):
                value_logits(self.hidden, binding, changed)

    def test_binding_cannot_claim_unavailable_row(self):
        binding = replace(self.bind(), abi_indices=(11, 8194))
        with self.assertRaises(BilqisError):
            value_logits(self.hidden, binding, self.banks)

    def test_label_identity_swap_rejects(self):
        original = self.bind()
        changed = replace(original, identities=original.identities[::-1],
                          abi_indices=original.abi_indices[::-1])
        with self.assertRaises(BilqisError):
            value_logits(self.hidden, changed, self.banks)

    def test_tied_bank_gradient_and_batched_shape(self):
        binding = self.bind('semantic_token', ('bank1',))
        def loss(weights):
            changed = (self.banks[0], replace(self.banks[1], weights=weights))
            return mx.sum(value_logits(mx.stack([self.hidden, self.hidden]), binding, changed).logits)
        gradient = mx.grad(loss)(self.banks[1].weights)
        self.assertEqual(float(gradient[1, 0]), 2.)
        self.assertEqual(float(mx.sum(mx.abs(gradient[2]))), 0.)
        self.assertTrue(bool(mx.all(mx.isfinite(gradient))))

    def test_malformed_hidden_rejects(self):
        for hidden in (mx.zeros((767,)), mx.zeros((768,), dtype=mx.float16)):
            with self.assertRaises(BilqisError):
                value_logits(hidden, self.bind(), self.banks)
