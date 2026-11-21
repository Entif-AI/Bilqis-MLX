from pathlib import Path
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator import session


def test_operate_runs_data_plane_maintenance_after_operator_returns():
    sentinel = object()

    with (
        patch.object(session, "_operate_impl", return_value=sentinel),
        patch.object(session, "_run_post_operator_maintenance") as cleanup,
    ):
        result = session.operate_bamf(
            Path("/tmp/bilqis-storage-lifecycle-fixture"),
            minutes=1,
            max_visits=1,
            source_prefetch_workers=0,
        )

    assert result is sentinel
    cleanup.assert_called_once_with(
        Path("/tmp/bilqis-storage-lifecycle-fixture"),
        progress=None,
    )


def test_post_operator_maintenance_defers_without_failing_the_session(tmp_path):
    progress = []
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "bamf-state.json").write_text("{}")
    with (
        patch("bilqis_mlx._data_plane.maintenance.maintenance_roots",
              return_value=(run_dir,)),
        patch("bilqis_mlx._data_plane.cli._maintenance",
              side_effect=ValueError("HUMAN_TRAINING_ACTIVE")),
        patch("bilqis_mlx.data_plane.data_plane"),
    ):
        result = session._run_post_operator_maintenance(
            run_dir, progress=progress.append)

    assert result is None
    assert progress == [
        "post-operator data-plane maintenance deferred: HUMAN_TRAINING_ACTIVE"
    ]
