"""A smaller lookup slice retains query identity and independent source gold."""
import unittest

from bilqis_mlx.source_adapters import event_frames, event_pairs
from bilqis_mlx.live_grade_c import registry_graph


class EventPairTests(unittest.TestCase):
    def test_balanced_fresh_pairs_preserve_the_queried_transition(self):
        graph = event_frames.expanded_graph(registry_graph())
        for cap in event_frames.SPECS:
            rows = event_pairs.draw(None, graph, seed=349, each=64, capability=cap)
            self.assertEqual(len({r['id'] for r in rows}), 64)
            self.assertEqual(sum(r['gold'] == 'TRUE' for r in rows), 32)
            self.assertTrue(all(len(r['record']['events']) == 2 for r in rows))
            self.assertTrue(all(event_pairs.check(r, graph=graph) for r in rows))
            for row in rows:
                record = row['record']
                event = next(e for e in record['events'] if e[0] == record['query'])
                value = event_frames.evaluate(event_frames.expression(graph, cap, *event[1:]))
                self.assertEqual(row['gold'], 'TRUE' if value else 'FALSE')
            wrong = {**rows[0], 'gold': 'FALSE' if rows[0]['gold'] == 'TRUE' else 'TRUE'}
            self.assertFalse(event_pairs.check(wrong, graph=graph))
            self.assertNotEqual([r['id'] for r in rows], [r['id'] for r in
                event_pairs.draw(None, graph, seed=350, each=64, capability=cap)])
