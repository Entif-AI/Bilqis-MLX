"""B05/B11 integration: real numerical groups never confer producer authority."""
import unittest

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.block_attnres import depth_select
from bilqis_mlx.runtime.tests.test_backbone_group_numerical import (
    SPEC, _params, _run,
)


class B05B11SafetyTests(unittest.TestCase):
    def test_executed_but_unadmitted_group_cannot_enable_public_selector(self):
        h0 = mx.arange(4 * SPEC.width, dtype=mx.float32).reshape(
            1, 4, SPEC.width) / 1000
        group = _run(h0, _params())
        self.assertEqual(group.admission_status, "UNADMITTED_NUMERICAL")
        with self.assertRaises(BilqisError) as caught:
            depth_select(group.hidden, (group,), None, None)
        self.assertEqual(
            caught.exception.context["reason"],
            "BLOCKED_PRODUCER_DEPENDENCY")


if __name__ == "__main__":
    unittest.main()
