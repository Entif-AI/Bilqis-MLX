"""Public frozen record constructors reject malformed boundary data."""
from dataclasses import replace
import unittest
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.learning.atlas_readout import (
    TypedHeadLogits, RoleCandidate, bind_value_head, compile_frame_output,
)
from bilqis_mlx.learning.atlas_readout.tests.helpers import snapshot, frame_release


class RecordTests(unittest.TestCase):
    def setUp(self):
        mx.set_default_device(mx.cpu)

    def test_value_binding_shape_and_adapter_reject(self):
        binding = bind_value_head('binary', ('FALSE', 'TRUE'), snapshot(), live_answer_registry())
        for changes in ({'adapter': None}, {'values': ()}, {'schema_version': 'old'},
                        {'abi_indices': (True, 12)}, {'modality_id': ''},
                        {'snapshot': object()}):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                replace(binding, **changes)

    def test_frame_domain_constructor_rejects(self):
        schema, released, features = frame_release()
        domain = compile_frame_output(schema, released, features)
        for changes in ({'feature_digest': 'x'}, {'schema_version': 'old'},
                        {'released_schemas': None}, {'modality_id': 'answer.binary/v1'}):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                replace(domain, **changes)

    def test_role_candidate_constructor_rejects(self):
        for args in (('', 1, 'agent', 0), ('frame', 0, 'agent', 0),
                     ('frame', 1, '', 0), ('frame', 1, 'agent', True),
                     ('frame', 1, 'agent', -1)):
            with self.subTest(args=args), self.assertRaises(BilqisError):
                RoleCandidate(*args)

    def test_output_record_rejects_missing_identity_and_nonfinite(self):
        output = TypedHeadLogits(mx.array([1.]), ('TRUE',), 'answer.binary/v1', 'a'*64)
        for changes in ({'modality_id': ''}, {'semantic_release': 'a'},
                        {'schema_version': 'old'}, {'candidates': ('TRUE', 'TRUE')},
                        {'logits': mx.array([float('nan')])}, {'candidates': (42,)}):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                replace(output, **changes)
