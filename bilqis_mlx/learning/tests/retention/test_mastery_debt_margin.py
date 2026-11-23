"""Configurable margin for regression-bearing mastery-debt trades."""
import unittest

from bilqis_mlx.learning.learning_experiment import Settings, decide


def _marginal_trade():
    return {
        "A.LINK": {"before": 2, "after": 3, "total": 6},
        "A.MAPS": {"before": 3, "after": 4, "total": 6},
        "A.EDGE": {"before": 5, "after": 3, "total": 6},
        "A.MEMBER": {"before": 5, "after": 4, "total": 6},
        "A.IDENTITY": {"before": 4, "after": 4, "total": 6},
        "A.PARENT": {"before": 4, "after": 4, "total": 6},
    }


class MasteryDebtMarginTests(unittest.TestCase):
    def _decide(self, paired, *, settings=Settings()):
        return decide(
            paired,
            active_capability="A.LINK",
            phase="RECOVERY_1",
            protected=set(paired) - {"A.LINK"},
            settings=settings,
            same_grade_capabilities=tuple(paired),
            plasticity_escape={"active": True},
        )

    def test_default_margin_rejects_recent_one_over_36_trade(self):
        result = self._decide(_marginal_trade())
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "PROTECTED_CAPABILITY_REGRESSION")

    def test_explicit_lower_margin_can_admit_same_trade(self):
        result = self._decide(
            _marginal_trade(),
            settings=Settings(mastery_debt_min_utility=0.02),
        )
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")

    def test_default_margin_preserves_material_positive_trade(self):
        result = self._decide({
            "A.LINK": {"before": 3, "after": 4, "total": 6},
            "A.MAPS": {"before": 3, "after": 4, "total": 6},
            "A.EDGE": {"before": 4, "after": 2, "total": 6},
            "A.MEMBER": {"before": 3, "after": 4, "total": 6},
            "A.IDENTITY": {"before": 3, "after": 3, "total": 6},
            "A.PARENT": {"before": 3, "after": 4, "total": 6},
        })
        self.assertEqual(result["decision"], "PROVISIONAL")

    def test_margin_does_not_block_no_regression_gain(self):
        result = self._decide({
            "A.LINK": {"before": 2, "after": 3, "total": 6},
            "A.MAPS": {"before": 3, "after": 3, "total": 6},
            "A.EDGE": {"before": 4, "after": 4, "total": 6},
        })
        self.assertEqual(result["decision"], "PROVISIONAL")


if __name__ == "__main__":
    unittest.main()
