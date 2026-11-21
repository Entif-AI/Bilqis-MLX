"""#1333 durable cadence terminal projection and explicit replay custody."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bilqis_mlx.data_plane import DataPlane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import active_grade_cadence_replay as replay
from bilqis_mlx.runtime.active_grade_cadence_replay import (
    authenticated_cadence_attempts,
    rebuild_authenticated_cadence_attempts,
)


def _cadence(capability="cap"):
    return {
        "schema": "bilqis.bamf.active-grade-cadence-authorization/v1",
        "phase": "MAIN", "phase_round": 0,
        "phase_sha256": "1" * 64, "cadence_sha256": "2" * 64,
        "active_grade_activation_sha256": "3" * 64,
        "active_grade_definition_sha256": "4" * 64,
        "member_census_sha256": "5" * 64,
        "deficit_evidence_sha256": "6" * 64,
        "policy_epoch": 1, "authorized_capability_ids": [capability],
        "disposition": "TEACHING",
    }


def _pointer(generation, manifest, acceptance="f" * 64, parent=None):
    return {
        "run_id": "run", "generation": generation,
        "manifest_sha256": manifest, "acceptance_sha256": acceptance,
        "parent_manifest_sha256": parent,
    }


def _student(generation, *, manifest_parent=None, outbox=()):
    return SimpleNamespace(
        run_id="run", generation=generation,
        parent_manifest_sha256=manifest_parent, outbox=tuple(outbox),
    )


def _rejection(cadence, generation=0):
    return {
        "event": "BAMF_CANDIDATE_REJECTED", "generation": generation,
        "evidence": {"schema": "bilqis.bamf.c16.3-rejection/v2",
                     "capability": "cap", "cadence": cadence},
    }


def test_explicit_rebuild_recovers_accepted_outbox_before_event_delivery(tmp_path):
    (tmp_path / "bamf-state.json").write_text("{}", encoding="utf-8")
    cadence = _cadence()
    event = {
        "event": "BAMF_C16_3_ACCEPTED", "parent_generation": 0,
        "accepted_manifest_sha256": "a" * 64, "capability": "cap",
        "cadence": cadence,
    }
    genesis = _student(0)
    child = _student(1, manifest_parent="a" * 64, outbox=(event,))
    chain = {0: (genesis, "a" * 64), 1: (child, "b" * 64)}
    pointer = _pointer(1, "b" * 64, parent="a" * 64)
    plane = DataPlane(tmp_path / "plane.sqlite3")
    try:
        with patch.object(replay, "_accepted_chain", return_value=chain), patch.object(
                replay, "_current_accepted", return_value=(pointer, child)), patch(
                    "bilqis_mlx.data_plane.data_plane", return_value=plane):
            attempts = rebuild_authenticated_cadence_attempts(tmp_path)
    finally:
        plane.close()
    assert attempts == ((cadence, "cap"),)


def test_explicit_rebuild_requires_authenticated_rejection_owner(tmp_path):
    (tmp_path / "bamf-state.json").write_text("{}", encoding="utf-8")
    cadence = _cadence()
    event = _rejection(cadence)
    (tmp_path / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    parent = _student(0)
    chain = {0: (parent, "a" * 64)}
    pointer = _pointer(0, "a" * 64)
    plane = DataPlane(tmp_path / "plane.sqlite3")
    try:
        with patch.object(replay, "_accepted_chain", return_value=chain), patch.object(
                replay, "_current_accepted", return_value=(pointer, parent)), patch(
                    "bilqis_mlx.data_plane.data_plane", return_value=plane), patch(
                        "bilqis_mlx.runtime.priority_rejection_replay."
                        "authenticated_rejection_event", return_value=True) as authenticate:
            attempts = rebuild_authenticated_cadence_attempts(tmp_path)
    finally:
        plane.close()
    assert attempts == ((cadence, "cap"),)
    authenticate.assert_called_once_with(event, parent, "a" * 64)


def test_cold_restart_restores_projection_and_reads_only_unseen_tail(tmp_path):
    (tmp_path / "bamf-state.json").write_text("{}", encoding="utf-8")
    ledger = tmp_path / "events.jsonl"
    ledger.write_text(json.dumps({"event": "OTHER"}) + "\n", encoding="utf-8")
    cadence = _cadence()
    pointer = _pointer(0, "a" * 64)
    student = _student(0)
    database = tmp_path / "plane.sqlite3"
    first_plane = DataPlane(database)
    with patch.object(replay, "_current_accepted", return_value=(pointer, student)), patch(
            "bilqis_mlx.data_plane.data_plane", return_value=first_plane), patch.object(
                replay, "_accepted_chain", side_effect=AssertionError("ordinary replay")):
        assert authenticated_cadence_attempts(tmp_path) == ()
    state = first_plane.event_projection_state(
        tmp_path, replay._PROJECTION_KEY, replay._PROJECTION_SCHEMA)
    frontier = state["indexed_bytes"]
    first_plane.close()

    event = _rejection(cadence)
    with ledger.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")
    second_plane = DataPlane(database)
    original_tail = second_plane.indexed_event_tail
    try:
        with patch.object(replay, "_current_accepted", return_value=(pointer, student)), patch(
                "bilqis_mlx.data_plane.data_plane", return_value=second_plane), patch.object(
                    replay, "_accepted_chain", side_effect=AssertionError("ordinary replay")), patch(
                        "bilqis_mlx.runtime.priority_rejection_replay."
                        "authenticated_rejection_event", return_value=True), patch.object(
                            second_plane, "indexed_event_tail", wraps=original_tail) as tail:
            assert authenticated_cadence_attempts(tmp_path) == ((cadence, "cap"),)
        tail.assert_called_once_with(tmp_path.resolve(), frontier)
    finally:
        second_plane.close()


def test_accepted_outbox_projection_survives_delivery_after_restart(tmp_path):
    (tmp_path / "bamf-state.json").write_text("{}", encoding="utf-8")
    ledger = tmp_path / "events.jsonl"
    ledger.write_text(json.dumps({"event": "OTHER"}) + "\n", encoding="utf-8")
    database = tmp_path / "plane.sqlite3"
    plane = DataPlane(database)
    genesis_pointer = _pointer(0, "a" * 64)
    genesis = _student(0)
    cadence = _cadence()
    event = {
        "event": "BAMF_C16_3_ACCEPTED", "parent_generation": 0,
        "accepted_manifest_sha256": "a" * 64, "capability": "cap",
        "cadence": cadence,
    }
    child_pointer = _pointer(1, "b" * 64, parent="a" * 64)
    child = _student(1, manifest_parent="a" * 64, outbox=(event,))
    try:
        with patch.object(replay, "_current_accepted", return_value=(genesis_pointer, genesis)), patch(
                "bilqis_mlx.data_plane.data_plane", return_value=plane):
            assert authenticated_cadence_attempts(tmp_path) == ()
        with patch.object(replay, "_current_accepted", return_value=(child_pointer, child)), patch(
                "bilqis_mlx.data_plane.data_plane", return_value=plane):
            assert authenticated_cadence_attempts(tmp_path) == ((cadence, "cap"),)
    finally:
        plane.close()

    with ledger.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")
    restarted = DataPlane(database)
    try:
        with patch.object(replay, "_current_accepted", return_value=(child_pointer, child)), patch(
                "bilqis_mlx.data_plane.data_plane", return_value=restarted), patch.object(
                    replay, "_accepted_chain", side_effect=AssertionError("ordinary replay")):
            assert authenticated_cadence_attempts(tmp_path) == ((cadence, "cap"),)
    finally:
        restarted.close()


def test_missing_projection_on_deep_history_requires_explicit_rebuild(tmp_path):
    (tmp_path / "bamf-state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"event": "OTHER"}) + "\n", encoding="utf-8")
    pointer = _pointer(2, "c" * 64, parent="b" * 64)
    student = _student(2, manifest_parent="b" * 64)
    plane = DataPlane(tmp_path / "plane.sqlite3")
    try:
        with patch.object(replay, "_current_accepted", return_value=(pointer, student)), patch(
                "bilqis_mlx.data_plane.data_plane", return_value=plane), patch.object(
                    replay, "_accepted_chain", side_effect=AssertionError("implicit replay")):
            with pytest.raises(BilqisError) as failure:
                authenticated_cadence_attempts(tmp_path)
    finally:
        plane.close()
    assert failure.value.context.get("reason") == replay._REBUILD_REQUIRED
