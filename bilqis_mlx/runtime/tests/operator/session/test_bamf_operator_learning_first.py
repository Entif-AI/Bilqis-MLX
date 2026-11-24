"""Focused routing checks for the learning-first BAMF candidate path."""
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.session_parts.native_session import (
    candidate_horizon_execution, execute_horizon,
)
from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
from bilqis_mlx.runtime.bamf_bundle.execution_cache import AcceptedExecutionCache


def _invalid(reason):
    raise ValueError(reason)


_AUTO_CACHE = object()


def _run_horizon(selection, captured, *, cache=_AUTO_CACHE):
    sentinel = object()

    def horizon_impl(*args, **kwargs):
        captured.update(kwargs)
        return sentinel

    with patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
            "_candidate_horizon_execution_impl",
            side_effect=horizon_impl), patch(
                "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
                "bind_current_retention_protection_plan"):
        result = candidate_horizon_execution(
            Path("/run"), object(), object(), "atlas", "features",
            selection, (), "A.TEST", object() if cache is _AUTO_CACHE else cache,
            12, None, 0, None, None,
            None, None, emit_progress=lambda *_args: None, invalid=_invalid)
    assert result is sentinel


def _executor_from(captured):
    closure = inspect.getclosurevars(captured["execute_horizon_fn"]).nonlocals
    return closure["candidate_executor"]


def _rehearsal_plan_from(captured):
    closure = inspect.getclosurevars(captured["execute_horizon_fn"]).nonlocals
    return closure["rehearsal_plan"]


def test_learning_first_horizon_never_prepares_strict_source_authority():
    selection = SimpleNamespace(status="TEACHER_SELECTED")
    captured = {}
    with evidence_mode(strict=False), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
            "prepare_accepted_priority_candidate_visit") as strict_prepare:
        _run_horizon(selection, captured)

    strict_prepare.assert_not_called()
    from bilqis_mlx.runtime.bamf_operator.session_parts import native_session
    assert _executor_from(captured) is native_session.execute_learning_first_priority_candidate


def test_learning_first_horizon_scopes_one_preparation_cache_to_the_candidate():
    from bilqis_mlx.runtime.bamf_operator.session_parts import native_session
    captured = {}

    def horizon_impl(*args, **kwargs):
        captured["execute_candidate"] = kwargs["execute_candidate"]
        return (), object()

    with patch.object(native_session, "_execute_horizon_impl", side_effect=horizon_impl):
        execute_horizon(
            Path("/run"), object(), object(), object(), "atlas", "features", (), 4,
            object(), 1, None, 0, None, None, None, None,
            emit_progress=lambda *_args: None, invalid=_invalid,
            candidate_executor=native_session.execute_learning_first_priority_candidate)

    executor = captured["execute_candidate"]
    assert isinstance(executor.keywords["learning_first_cache"], LearningFirstPreparationCache)


def test_learning_first_horizon_preserves_rehearsal_with_accepted_cache():
    selection = SimpleNamespace(status="TEACHER_SELECTED")
    accepted_cache = object.__new__(AcceptedExecutionCache)
    rehearsal_plan = object()
    captured = {}
    with evidence_mode(strict=False), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
            "compile_rehearsal_plan", return_value=rehearsal_plan) as compile_plan:
        _run_horizon(selection, captured, cache=accepted_cache)

    compile_plan.assert_called_once()
    assert _rehearsal_plan_from(captured) is rehearsal_plan


def test_learning_first_horizon_never_rebinds_missing_session_cache():
    selection = SimpleNamespace(status="TEACHER_SELECTED")
    with evidence_mode(strict=False), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
            "bind_accepted_execution_cache",
            side_effect=AssertionError("non-strict cache rebound")) as bind_cache:
        with pytest.raises(ValueError, match="BAMF_LEARNING_FIRST_SESSION_CACHE_REQUIRED"):
            _run_horizon(selection, {}, cache=None)
    bind_cache.assert_not_called()


def test_learning_first_horizon_fails_closed_when_accepted_rehearsal_plan_is_invalid():
    selection = SimpleNamespace(status="TEACHER_SELECTED")
    accepted_cache = object.__new__(AcceptedExecutionCache)
    with evidence_mode(strict=False), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
            "compile_rehearsal_plan", side_effect=ValueError("rehearsal-invalid")):
        with pytest.raises(ValueError, match="rehearsal-invalid"):
            _run_horizon(selection, {}, cache=accepted_cache)


def test_strict_horizon_preserves_legacy_source_authority_path():
    selection = SimpleNamespace(status="TEACHER_SELECTED")
    captured = {}
    with evidence_mode(strict=True), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
            "prepare_accepted_priority_candidate_visit",
            return_value=object()) as strict_prepare:
        _run_horizon(selection, captured)

    strict_prepare.assert_called_once()
    from bilqis_mlx.runtime.bamf_operator.session_parts import native_session
    assert _executor_from(captured) is native_session.execute_accepted_priority_candidate


def test_strict_horizon_preserves_rehearsal_with_accepted_cache():
    selection = SimpleNamespace(status="TEACHER_SELECTED")
    accepted_cache = object.__new__(AcceptedExecutionCache)
    rehearsal_plan = object()
    captured = {}
    with evidence_mode(strict=True), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
            "compile_rehearsal_plan", return_value=rehearsal_plan) as compile_plan, patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
            "prepare_accepted_priority_candidate_visit", return_value=object()):
        _run_horizon(selection, captured, cache=accepted_cache)

    compile_plan.assert_called_once()
    assert _rehearsal_plan_from(captured) is rehearsal_plan
    from bilqis_mlx.runtime.bamf_operator.session_parts import native_session
    assert _executor_from(captured) is native_session.execute_accepted_priority_candidate
