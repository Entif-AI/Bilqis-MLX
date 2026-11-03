"""Exact binding error code and source geometry."""
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_schema import SourceSpan, _binding_fail


class BindingErrorTests(TestCase):
    def test_binding_error_preserves_reason_span_and_role(self):
        with self.assertRaises(BilqisError) as caught:
            _binding_fail("FRAME_SCOPE_MISMATCH", SourceSpan(8, 12), "agent")
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.BINDING.INVALID")
        self.assertEqual(caught.exception.context, {
            "reason": "FRAME_SCOPE_MISMATCH", "span_start": 8,
            "span_end": 12, "role_id": "agent"})
