"""Cold-cache invariants for native CURRENT projection."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane.native_contracts import NativeProjectionMaterial
from bilqis_mlx.control_plane.native_source import native_query_source


class NativeQueryCacheTests(unittest.TestCase):
    def test_heartbeat_does_not_prevent_base_cache_warmup(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bamf-state.json").write_text("{}", encoding="utf-8")
            observation = root / "trainer-observed.json"
            observation.write_text("{}", encoding="utf-8")
            material = NativeProjectionMaterial((), (), (), {})
            mutated = False

            def materialize(*_args, **_kwargs):
                nonlocal mutated
                if not mutated:
                    observation.write_text(
                        '{"heartbeat":1}', encoding="utf-8")
                    mutated = True
                return material

            with (
                    patch(
                        "bilqis_mlx.control_plane.native_source.authenticated_history",
                        return_value=("accepted-history",)) as authenticate,
                    patch(
                        "bilqis_mlx.control_plane.native_source."
                        "_materialize_authenticated_history",
                        side_effect=materialize),
                    patch(
                        "bilqis_mlx.control_plane.native_source._run_refs",
                        return_value=("run-ref",)),
                    patch(
                        "bilqis_mlx.control_plane.native_source.observed_records",
                        return_value=())):
                source = native_query_source(root)
                source()
                source()

            self.assertEqual(authenticate.call_count, 1)


    def test_pointer_race_never_caches_old_history_under_new_identity(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pointer = root / "bamf-state.json"
            pointer.write_text("old", encoding="utf-8")
            material = NativeProjectionMaterial((), (), (), {})
            histories = []

            def materialize(_root, history, **_kwargs):
                histories.append(history)
                if history == ("old",):
                    pointer.write_text("new generation", encoding="utf-8")
                return material

            with (
                    patch(
                        "bilqis_mlx.control_plane.native_source.authenticated_history",
                        side_effect=[("old",), ("new",)]) as authenticate,
                    patch(
                        "bilqis_mlx.control_plane.native_source."
                        "_materialize_authenticated_history", side_effect=materialize)):
                source = native_query_source(root)
                self.assertFalse(source().available)
                self.assertTrue(source().available)
                self.assertEqual(source._native_material(), material)
                self.assertEqual(authenticate.call_count, 2)
                self.assertEqual(histories, [("old",), ("new",)])

if __name__ == "__main__":
    unittest.main()
