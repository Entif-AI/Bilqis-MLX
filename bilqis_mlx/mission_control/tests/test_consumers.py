"""Terminal and GUI fixtures consume the same immutable OperatorView."""
import unittest

from bilqis_mlx.mission_control.codec import decode_record
from bilqis_mlx.mission_control.fixtures import (
    gui_status_fixture, representative_operator_view, terminal_status,
)


class MissionControlConsumerFixtureTests(unittest.TestCase):
    def test_terminal_and_gui_share_one_record_identity_and_run_binding(self):
        view = representative_operator_view()
        terminal = terminal_status(view)
        gui = gui_status_fixture(view)
        decoded = decode_record(gui["record"])
        self.assertEqual(decoded, view)
        self.assertIn("run=fixture-run generation=7", terminal)
        self.assertIn("record=operator-view:fixture-run:7", terminal)
        self.assertEqual(gui["kind"], "operator-status")
        self.assertEqual(gui["record"]["meta"]["record_id"], view.meta.record_id)
        self.assertEqual(gui["record"]["meta"]["run"]["generation"], 7)


if __name__ == "__main__":
    unittest.main()
