import unittest

from bilqis_mlx.runtime.mlx_memory import training_memory_policy


class FakeMlx:
    def __init__(self, cache_limit=123, memory_limit=456, wired_limit=789):
        self.cache_limit = cache_limit
        self.memory_limit = memory_limit
        self.wired_limit = wired_limit
        self.calls = []

    def set_cache_limit(self, value):
        previous = self.cache_limit
        self.cache_limit = value
        self.calls.append(("set_cache_limit", value))
        return previous

    def clear_cache(self):
        self.calls.append(("clear_cache",))

    def set_memory_limit(self, value):
        previous = self.memory_limit
        self.memory_limit = value
        self.calls.append(("set_memory_limit", value))
        return previous

    def set_wired_limit(self, value):
        previous = self.wired_limit
        self.wired_limit = value
        self.calls.append(("set_wired_limit", value))
        return previous


class TrainingMemoryPolicyTests(unittest.TestCase):
    def test_training_applies_twelve_gib_allocator_and_wired_policy(self):
        mx = FakeMlx(memory_limit=111, wired_limit=222)

        with training_memory_policy(mx) as policy:
            self.assertEqual(mx.memory_limit, 12 * 1024**3)
            self.assertEqual(mx.wired_limit, 12 * 1024**3)
            self.assertEqual(policy["memory_ceiling_bytes"], 12 * 1024**3)

        self.assertEqual(mx.memory_limit, 111)
        self.assertEqual(mx.wired_limit, 222)

    def test_training_disables_free_buffer_cache_and_restores_prior_policy(self):
        mx = FakeMlx(cache_limit=987654)

        with training_memory_policy(mx):
            self.assertEqual(mx.cache_limit, 0)
            self.assertEqual(
                mx.calls,
                [
                    ("set_memory_limit", 12 * 1024**3),
                    ("set_wired_limit", 12 * 1024**3),
                    ("set_cache_limit", 0),
                    ("clear_cache",),
                ],
            )

        self.assertEqual(mx.cache_limit, 987654)
        self.assertEqual(
            mx.calls,
            [
                ("set_memory_limit", 12 * 1024**3),
                ("set_wired_limit", 12 * 1024**3),
                ("set_cache_limit", 0),
                ("clear_cache",),
                ("clear_cache",),
                ("set_cache_limit", 987654),
                ("set_wired_limit", 789),
                ("set_memory_limit", 456),
            ],
        )

    def test_training_restores_memory_policy_after_exception(self):
        mx = FakeMlx(cache_limit=321)

        with self.assertRaisesRegex(RuntimeError, "boom"):
            with training_memory_policy(mx):
                raise RuntimeError("boom")

        self.assertEqual(mx.cache_limit, 321)
        self.assertEqual(mx.calls[-4:], [
            ("clear_cache",), ("set_cache_limit", 321),
            ("set_wired_limit", 789), ("set_memory_limit", 456),
        ])


if __name__ == "__main__":
    unittest.main()
