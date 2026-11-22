"""Cold-cache invariants for native CURRENT projection."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane.native_contracts import NativeProjectionMaterial
from bilqis_mlx.control_plane.native_source import native_query_source
from bilqis_mlx.mission_control import (
    MissionControlQueryCatalog, QueryFamily, QueryMode, QueryRequest,
)


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


    def test_composed_source_forwards_query_identity_to_native_source(self):
        from bilqis_mlx.control_plane.__main__ import _composed_query_source

        seen = []

        def native(request=None):
            seen.append(request)
            return MissionControlQueryCatalog(())

        native._bilqis_query_aware = True
        projection = SimpleNamespace(notifications=lambda: ())
        request = QueryRequest(
            QueryFamily.RUN, mode=QueryMode.HISTORICAL,
            run_id="run", generation=7)
        with (
                patch(
                    "bilqis_mlx.control_plane.__main__.native_query_source",
                    return_value=native),
                patch(
                    "bilqis_mlx.control_plane.__main__.sync_akasha_notifications"),
                patch(
                    "bilqis_mlx.control_plane.__main__."
                    "sync_native_transition_notifications")):
            source = _composed_query_source(Path("."), projection)
            self.assertTrue(getattr(source, "_bilqis_query_aware", False))
            source(request)

        self.assertEqual(seen, [request])



if __name__ == "__main__":
    unittest.main()
