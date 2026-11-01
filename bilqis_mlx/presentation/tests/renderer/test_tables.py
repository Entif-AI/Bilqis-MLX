"""Public terminal column records retain historical serialization identity."""
import pickle
import unittest

from bilqis_mlx.presentation.spiral_dashboard import Column, Dashboard, TABLES


class TablesTests(unittest.TestCase):
    def test_historical_column_pickle_round_trips(self):
        column = Column("GRADE", 5, "grade", optional=True, right=True)
        self.assertEqual(Column.__module__, "bilqis_mlx.presentation.spiral_dashboard")
        self.assertEqual(pickle.loads(pickle.dumps(column)), column)
        self.assertEqual(TABLES[0][1][0], Column("GRADE", 5, "grade"))

    def test_dashboard_keeps_public_class_identity(self):
        self.assertEqual(Dashboard.__module__, "bilqis_mlx.presentation.spiral_dashboard")
