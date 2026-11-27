import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.memory_safety import (
    GIB,
    MIB,
    MemoryPlateauPolicy,
    MemoryPlateauSample,
    TrainerMemoryPolicy,
    assess_memory_plateau,
)


class TrainerMemoryPolicyTests(unittest.TestCase):
    def test_default_policy_reserves_trip_headroom_below_twelve_gib_ceiling(self):
        policy = TrainerMemoryPolicy.from_gib(12)

        self.assertEqual(policy.ceiling_bytes, 12 * GIB)
        self.assertEqual(policy.warning_bytes, 10 * GIB)
        self.assertEqual(policy.trip_bytes, 11 * GIB)
        self.assertEqual(policy.sample_interval_seconds, 0.02)

    def test_policy_refuses_more_than_sixteen_gib(self):
        with self.assertRaises(BilqisError) as raised:
            TrainerMemoryPolicy.from_gib(17)
        self.assertEqual(raised.exception.code, SCHOOL.BAMF_RESOURCES.INVALID.code)
        self.assertEqual(
            raised.exception.context["reason"], "BAMF_MEMORY_CEILING_INVALID")


class MemoryPlateauTests(unittest.TestCase):
    def _samples(self, gib_values):
        return tuple(
            MemoryPlateauSample(
                ordinal=index,
                physical_footprint_bytes=int(value * GIB),
                python_heap_bytes=64 * MIB,
                mlx_active_bytes=int(value * GIB),
                live_mlx_bytes=1 * GIB,
            )
            for index, value in enumerate(gib_values, start=1)
        )

    def test_stable_low_water_passes(self):
        result = assess_memory_plateau(self._samples(
            (2.0, 2.2, 2.10, 2.14, 2.11, 2.16, 2.12, 2.15)))

        self.assertTrue(result.plateau)
        self.assertLessEqual(result.net_growth_bytes, 512 * MIB)

    def test_incrementally_rising_low_water_fails_even_when_each_cycle_reclaims_memory(self):
        result = assess_memory_plateau(
            self._samples((2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5)),
            MemoryPlateauPolicy(
                warmup_samples=2,
                min_samples=6,
                max_net_growth_bytes=512 * MIB,
                max_slope_bytes_per_sample=128 * MIB,
            ),
        )

        self.assertFalse(result.plateau)
        self.assertIn("positive retained-memory slope", result.reasons)

    def test_unattributed_mlx_growth_is_reported(self):
        samples = self._samples((2.0, 2.1, 2.2, 2.3, 2.4, 2.5))
        result = assess_memory_plateau(samples)

        self.assertEqual(
            result.last_unattributed_mlx_bytes,
            samples[-1].mlx_active_bytes - samples[-1].live_mlx_bytes,
        )


if __name__ == "__main__":
    unittest.main()
