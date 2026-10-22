"""Query-swap diagnostics expose a predictor that ignores the query."""
import unittest

from scripts.issue349_query_probe import query_pair_scores


class QueryPairScoreTests(unittest.TestCase):
    def test_query_blind_accuracy_does_not_count_as_a_correct_pair(self):
        pairs = [({'id': 'a', 'gold': 'TRUE'}, {'id': 'b', 'gold': 'FALSE'})]
        self.assertEqual(query_pair_scores(pairs, {'a': 'TRUE', 'b': 'TRUE'}),
                         dict(opposite_query_pairs=1, both_queries_correct=0, predictions_flip=0))
        self.assertEqual(query_pair_scores(pairs, {'a': 'TRUE', 'b': 'FALSE'}),
                         dict(opposite_query_pairs=1, both_queries_correct=1, predictions_flip=1))
        self.assertEqual(query_pair_scores(pairs, {'a': 'FALSE', 'b': 'TRUE'}),
                         dict(opposite_query_pairs=1, both_queries_correct=0, predictions_flip=1))
