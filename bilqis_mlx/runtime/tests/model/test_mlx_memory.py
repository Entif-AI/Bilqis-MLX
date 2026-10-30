import unittest

from bilqis_mlx.runtime.mlx_memory import training_memory_policy


class FakeMlx:
    def __init__(self, cache_limit=123):
        self.cache_limit = cache_limit
        self.calls = []

    def set_cache_limit(self, value):
        previous = self.cache_limit
        self.cache_limit = value
        self.calls.append(("set_cache_limit", value))
        return previous

    def clear_cache(self):
        self.calls.append(("clear_cache",))


class TrainingMemoryPolicyTests(unittest.TestCase):
    def test_training_disables_free_buffer_cache_and_restores_prior_policy(self):
        mx = FakeMlx(cache_limit=987654)

        with training_memory_policy(mx):
            self.assertEqual(mx.cache_limit, 0)
            self.assertEqual(
                mx.calls,
                [("set_cache_limit", 0), ("clear_cache",)],
            )

        self.assertEqual(mx.cache_limit, 987654)
        self.assertEqual(
            mx.calls,
            [
                ("set_cache_limit", 0),
                ("clear_cache",),
                ("clear_cache",),
                ("set_cache_limit", 987654),
            ],
        )

    def test_training_restores_memory_policy_after_exception(self):
        mx = FakeMlx(cache_limit=321)

        with self.assertRaisesRegex(RuntimeError, "boom"):
            with training_memory_policy(mx):
                raise RuntimeError("boom")

        self.assertEqual(mx.cache_limit, 321)
        self.assertEqual(mx.calls[-2:], [("clear_cache",), ("set_cache_limit", 321)])


if __name__ == "__main__":
    unittest.main()
