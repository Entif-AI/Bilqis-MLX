"""C16.3 persistent BAMF operator routing contracts."""
from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_operator.session import (
    operate_bamf,
)


class BamfOperatorRoutingTests(unittest.TestCase):
    def test_session_fails_closed_before_any_visit_without_c03_priority_authority(self):
        with TemporaryDirectory() as temporary:
            with patch(
                "bilqis_mlx.runtime.bamf_operator.session._execution_context",
                return_value=(object(), object(), object(), object()),
            ) as context:
                with self.assertRaises(BilqisError) as caught:
                    operate_bamf(
                        temporary, minutes=1, max_visits=1, reserve_gib=0.0)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_OPERATOR_PRIORITY_AUTHORITY_UNAVAILABLE")
        context.assert_called_once()


if __name__ == "__main__":
    unittest.main()
