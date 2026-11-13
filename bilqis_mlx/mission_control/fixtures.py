"""Shared terminal/GUI fixture proving both clients consume one record family."""
from __future__ import annotations

from .codec import encode_record
from .model import AuthorityClass, CoverageState, RecordMeta, RunRef
from .snapshots import OperatorView


_D1 = "1" * 64
_D2 = "2" * 64
_D3 = "3" * 64
_D4 = "4" * 64


def representative_operator_view() -> OperatorView:
    run = RunRef(
        run_id="fixture-run",
        run_identity_sha256=_D4,
        generation=7,
        generation_manifest_sha256=_D1,
        candidate_identity_sha256=_D2,
        factory_release_sha256=_D2,
        semantic_release_sha256=_D3,
        topology_sha256=_D4,
    )
    meta = RecordMeta(
        record_id="operator-view:fixture-run:7",
        run=run,
        materialized_at=120,
        observed_at=118,
        as_of=118,
        coverage=CoverageState.COMPLETE,
        authority=AuthorityClass.DERIVED,
        source_refs=("run-state:fixture-run:7",),
        evidence_refs=("evidence:fixture-run:7",),
        receipt_refs=("receipt:fixture-run:7",),
    )
    return OperatorView(
        meta=meta,
        learner_state="READY",
        stage="ASSESS_MAIN",
        active_capability_id="B.EXAMPLE",
        related_record_ids=("school:fixture-run:7",),
    )


def terminal_status(view: OperatorView) -> tuple[str, ...]:
    """Tiny terminal consumer, deliberately not a second status model."""
    run = view.meta.run
    if type(view) is not OperatorView or run is None:
        raise TypeError
    return (
        f"run={run.run_id} generation={run.generation}",
        f"state={view.learner_state} stage={view.stage}",
        f"record={view.meta.record_id}",
    )


def gui_status_fixture(view: OperatorView) -> dict:
    """GUI-facing fixture payload; layout remains GUI01+ ownership."""
    if type(view) is not OperatorView:
        raise TypeError
    return {"kind": "operator-status", "record": encode_record(view)}
