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
        expected_token=None,
    )


def test_operate_runs_data_plane_maintenance_after_operator_crashes():
    failure = RuntimeError("trainer exploded")

    with (
        patch.object(session, "_operate_impl", side_effect=failure),
        patch.object(session, "_run_post_operator_maintenance") as cleanup,
    ):
        try:
            session.operate_bamf(
                Path("/tmp/bilqis-storage-lifecycle-fixture"),
                minutes=1,
                max_visits=1,
                source_prefetch_workers=0,
            )
        except RuntimeError as error:
            assert error is failure
        else:
            raise AssertionError("trainer failure was swallowed")

    cleanup.assert_called_once_with(
        Path("/tmp/bilqis-storage-lifecycle-fixture"),
        progress=None,
        expected_token=None,
    )


def test_cleanup_failure_never_masks_trainer_failure():
    trainer_failure = RuntimeError("trainer exploded")

    with (
        patch.object(session, "_operate_impl", side_effect=trainer_failure),
        patch.object(
            session, "_run_post_operator_maintenance",
            side_effect=ValueError("cleanup exploded"),
        ),
    ):
        try:
            session.operate_bamf(
                Path("/tmp/bilqis-storage-lifecycle-fixture"),
                minutes=1,
                max_visits=1,
                source_prefetch_workers=0,
            )
        except RuntimeError as error:
            assert error is trainer_failure
        else:
            raise AssertionError("trainer failure was swallowed")


def test_pending_cleanup_is_replayed_before_next_operator_attempt(tmp_path):
    token = "prior-crash-token"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "bamf-state.json").write_text("{}")
    with (
        patch(
            "bilqis_mlx._data_plane.maintenance_lifecycle.maintenance_pending_token",
            return_value=token,
        ),
        patch("bilqis_mlx.data_plane.data_plane"),
        patch.object(session, "_run_post_operator_maintenance") as cleanup,
    ):
        session._run_pending_operator_maintenance(run_dir)

    cleanup.assert_called_once_with(
        run_dir, progress=None, expected_token=token)


def test_current_operator_epoch_token_flows_to_final_cleanup(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "bamf-state.json").write_text("{}")
    sentinel = object()
    token = "current-epoch-token"

    def operate_impl(*_args, **kwargs):
        kwargs["before_visits"](run_dir)
        return sentinel

    with (
        patch.object(session, "_run_pending_operator_maintenance"),
        patch.object(session, "_operate_impl", side_effect=operate_impl),
        patch(
            "bilqis_mlx._data_plane.maintenance_lifecycle.mark_maintenance_pending",
            return_value=token,
        ),
        patch("bilqis_mlx.data_plane.data_plane"),
        patch.object(session, "_run_post_operator_maintenance") as cleanup,
    ):
        result = session.operate_bamf(
            run_dir, minutes=1, max_visits=1, source_prefetch_workers=0)

    assert result is sentinel
    cleanup.assert_called_once_with(
        run_dir, progress=None, expected_token=token)


def test_successful_cleanup_clears_only_the_serviced_epoch(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "bamf-state.json").write_text("{}")
    plane = object()
    result = {
        "gc": {},
        "file_gc": {},
    }
    with (
        patch(
            "bilqis_mlx._data_plane.maintenance.maintenance_roots",
            return_value=(run_dir,),
        ),
        patch("bilqis_mlx._data_plane.cli._maintenance", return_value=result),
        patch("bilqis_mlx.data_plane.data_plane", return_value=plane),
        patch(
            "bilqis_mlx._data_plane.maintenance_lifecycle.clear_maintenance_pending",
        ) as clear,
    ):
        observed = session._run_post_operator_maintenance(
            run_dir, expected_token="current-token")

    assert observed is result
    clear.assert_called_once_with(plane, run_dir, "current-token")


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
