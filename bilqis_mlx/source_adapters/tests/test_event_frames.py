"""Cheap truth, encoding and fresh-example checks for the exploratory tranche."""
import unittest
from bilqis_mlx.source_adapters import event_frames as frames
from bilqis_mlx.verification.event_frames import independent_answer
from bilqis_mlx.live_grade_c import registry_graph


class EventFrameTests(unittest.TestCase):
    def test_three_candidates_share_one_generator_and_checked_codec(self):
        graph = frames.expanded_graph(registry_graph())
        for capability in frames.SPECS:
            rows = frames.draw(None, graph, seed=349, each=32, capability=capability)
            self.assertEqual(len(rows), 32)
            self.assertEqual(sum(r['gold'] == 'TRUE' for r in rows), 16)
            self.assertTrue(all(frames.check(row, graph=graph) for row in rows))
            self.assertEqual(len({r['id'] for r in rows}), 32)
            changed = {**rows[0], 'gold': 'FALSE' if rows[0]['gold']=='TRUE' else 'TRUE'}
            self.assertFalse(frames.check(changed, graph=graph))
            fresh = frames.draw(None, graph, seed=350, each=32, capability=capability)
            self.assertNotEqual([r['id'] for r in rows], [r['id'] for r in fresh])

    def test_start_and_end_require_opposite_transition_directions(self):
        expected = {'D.EVENT_OCCURRENCE': (False, True, False, True),
                    'D.COMMENCEMENT': (False, True, False, False),
                    'D.TERMINATION': (False, False, True, False)}
        for cap, answers in expected.items():
            for (before, after), answer in zip(((False,False),(False,True),(True,False),(True,True)), answers):
                record = dict(task=frames.DIALECT, events=[['E0',before,after]],
                              capability=cap, query='E0')
                self.assertEqual(independent_answer(record), 'TRUE' if answer else 'FALSE')
