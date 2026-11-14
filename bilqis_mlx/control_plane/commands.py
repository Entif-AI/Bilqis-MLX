"""CP05 idempotent command admission, dispatch, and reconciliation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control.model import (
    AuthorityClass, CoverageState, MissionControlContractError, RecordMeta,
)
from bilqis_mlx.mission_control.operator import (
    ActionReceiptState, OperatorActionReceiptV2, OperatorActionRequestV2,
)

from .command_executor import C11CommandExecutor
from .command_launch import launch_command_worker
from .command_model import (
    CommandMode, ResolvedCommandTarget, intent_sha256, operation_id_for,
)
from .command_store import CommandStore
from .transport import _invalid


def _now() -> int:
    return int(time.time() * 1000)


def _error_ref(code: str, detail: object = None) -> str:
    raw = json.dumps(
        {"code": code, "detail": detail},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return "command-error:" + hashlib.sha256(raw).hexdigest()


def error_ref_from_exception(error: Exception) -> str:
    if isinstance(error, BilqisError):
        return _error_ref(error.code, dict(error.context))
    return _error_ref(type(error).__name__, str(error))


def _minimal_target(run_dir: Path) -> ResolvedCommandTarget:
    return ResolvedCommandTarget(
        run_dir=str(Path(run_dir).expanduser().resolve()),
        run_id=None,
        run_seed=None,
        run_identity_sha256=None,
        generation=None,
        generation_manifest_sha256=None,
        optimizer_step=None,
        candidate_identity_sha256=None,
        factory_release_sha256=None,
        semantic_release_sha256=None,
        topology_sha256=None,
        acceptance_sha256=None,
        source_identity=None,
    )


def build_receipt(
    request: OperatorActionRequestV2, *, operation_id: str,
    request_sha256: str, state: ActionReceiptState,
    target_ref: str, postcondition_ref: str | None = None,
    error_ref: str | None = None, receipt_refs: tuple[str, ...] = (),
) -> OperatorActionReceiptV2:
    timestamp = _now()
    meta = RecordMeta(
        record_id=f"cp05:{operation_id}:{state.value.lower()}",
        run=None,
        materialized_at=timestamp,
        observed_at=timestamp,
        as_of=timestamp,
        coverage=CoverageState.COMPLETE,
        authority=AuthorityClass.DERIVED,
        source_refs=("authority:c11-bamf-operator",),
        evidence_refs=(target_ref,),
        receipt_refs=receipt_refs,
    )
    return OperatorActionReceiptV2(
        meta=meta,
        request_id=request.request_id,
        request_sha256=request_sha256,
        operation_id=operation_id,
        state=state,
        acknowledged_at=timestamp,
        target_ref=target_ref,
        postcondition_ref=postcondition_ref,
        error_ref=error_ref,
    )


def _pid_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class CommandManager:
    """Exactly-once admission decision with at-most-once effect dispatch."""

    def __init__(
        self, run_dir: Path, store_root: Path, *,
        executor=None, launcher=None,
    ):
        self.run_dir = Path(run_dir).expanduser().resolve()
        self.store = CommandStore(store_root)
        self.executor = executor or C11CommandExecutor(self.run_dir)
        self.launcher = launcher or (
            lambda operation_id: launch_command_worker(
                store_root=self.store.root,
                run_dir=self.run_dir,
                operation_id=operation_id,
            )
        )

    def _rejection(
        self, request: OperatorActionRequestV2, operation_id: str,
        error: Exception | str, *, target: ResolvedCommandTarget | None = None,
    ) -> OperatorActionReceiptV2:
        target = target or _minimal_target(self.run_dir)
        ref = (
            _error_ref(error)
            if isinstance(error, str)
            else error_ref_from_exception(error)
        )
        return build_receipt(
            request,
            operation_id=operation_id,
            request_sha256=self._request_digest(request),
            state=ActionReceiptState.REJECTED,
            target_ref=target.ref,
            error_ref=ref,
        )

    @staticmethod
    def _request_digest(request: OperatorActionRequestV2) -> str:
        from .command_model import request_sha256
        return request_sha256(request)

    def submit(
        self, request: OperatorActionRequestV2,
    ) -> OperatorActionReceiptV2:
        if type(request) is not OperatorActionRequestV2:
            _invalid("CONTROL_PLANE_COMMAND_REQUEST_INVALID")
        operation_id = operation_id_for(request.idempotency_key)
        semantic = intent_sha256(request)
        with self.store.submission_lock():
            try:
                self.store.bind_request_id(
                    request.request_id, operation_id, semantic)
            except BilqisError as error:
                return self._rejection(request, operation_id, error)
        with self.store.operation_lock(operation_id):
            existing = self.store.read_submission(operation_id)
            if existing is not None:
                return self._retry_locked(
                    request, operation_id, semantic, existing)
            return self._admit_new_locked(
                request, operation_id, semantic)

    def _retry_locked(
        self, request, operation_id: str, semantic: str, existing,
    ) -> OperatorActionReceiptV2:
        _accepted_request, _raw_sha, existing_intent = existing
        if existing_intent != semantic:
            return self._rejection(
                request,
                operation_id,
                "CONTROL_PLANE_COMMAND_IDEMPOTENCY_CONFLICT",
                target=self._target_for(operation_id),
            )
        return self._status_locked(operation_id)

    def _admit_new_locked(
        self, request: OperatorActionRequestV2, operation_id: str, semantic: str,
    ) -> OperatorActionReceiptV2:
        self.store.write_submission(operation_id, request)
        try:
            plan, preflight = self.executor.preflight(request, operation_id)
        except (BilqisError, MissionControlContractError, OSError) as error:
            return self._persist_preflight_rejection(
                request, operation_id, error)
        if plan.intent_sha256 != semantic:
            _invalid("CONTROL_PLANE_COMMAND_PLAN_IDENTITY_DRIFT")
        self.store.write_plan(plan)
        self.store.write_preflight(operation_id, preflight)
        accepted = build_receipt(
            request,
            operation_id=operation_id,
            request_sha256=plan.request_sha256,
            state=ActionReceiptState.ACCEPTED,
            target_ref=plan.target.ref,
        )
        self.store.write_accepted(operation_id, accepted)
        if plan.mode is not CommandMode.MUTATING:
            return self._complete_inert_locked(
                request, operation_id, plan, preflight)
        return self._dispatch_locked(
            request, operation_id, plan, accepted)

    def _persist_preflight_rejection(
        self, request, operation_id: str, error: Exception,
    ) -> OperatorActionReceiptV2:
        target = _minimal_target(self.run_dir)
        self.store.write_preflight(operation_id, {
            "kind": "rejected-preflight",
            "target": target.to_record(),
            "error_ref": error_ref_from_exception(error),
        })
        terminal = self._rejection(
            request, operation_id, error, target=target)
        self.store.write_terminal(operation_id, terminal)
        return terminal

    def _complete_inert_locked(
        self, request, operation_id: str, plan, preflight: dict,
    ) -> OperatorActionReceiptV2:
        try:
            postcondition = self.executor.inert_postcondition(plan, preflight)
            postcondition_ref = self.store.write_postcondition(
                operation_id, postcondition)
        except (BilqisError, MissionControlContractError, OSError) as error:
            terminal = build_receipt(
                request,
                operation_id=operation_id,
                request_sha256=plan.request_sha256,
                state=ActionReceiptState.FAILED,
                target_ref=plan.target.ref,
                error_ref=error_ref_from_exception(error),
            )
            self.store.write_terminal(operation_id, terminal)
            return terminal
        terminal = build_receipt(
            request,
            operation_id=operation_id,
            request_sha256=plan.request_sha256,
            state=ActionReceiptState.COMPLETED,
            target_ref=plan.target.ref,
            postcondition_ref=postcondition_ref,
            receipt_refs=(f"command-plan:{plan.digest}", postcondition_ref),
        )
        self.store.write_terminal(operation_id, terminal)
        return terminal

    def _dispatch_locked(
        self, request, operation_id: str, plan,
        accepted: OperatorActionReceiptV2,
    ) -> OperatorActionReceiptV2:
        try:
            self.store.write_dispatch(operation_id, reserved_at=_now())
        except (BilqisError, OSError):
            return accepted
        try:
            pid = self.launcher(operation_id)
        except OSError as error:
            terminal = build_receipt(
                request,
                operation_id=operation_id,
                request_sha256=plan.request_sha256,
                state=ActionReceiptState.FAILED,
                target_ref=plan.target.ref,
                error_ref=error_ref_from_exception(error),
            )
            self.store.write_terminal(operation_id, terminal)
            return terminal
        try:
            self.store.write_spawned(
                operation_id, pid=pid, spawned_at=_now())
        except (BilqisError, OSError):
            return accepted
        return accepted

    def _target_for(self, operation_id: str) -> ResolvedCommandTarget:
        plan = self.store.read_plan(operation_id)
        return plan.target if plan is not None else _minimal_target(self.run_dir)

    def status(self, operation_id: str) -> OperatorActionReceiptV2:
        with self.store.operation_lock(operation_id):
            return self._status_locked(operation_id)

    def _status_locked(self, operation_id: str) -> OperatorActionReceiptV2:
        terminal = self.store.read_terminal(operation_id)
        if terminal is not None:
            return terminal
        submission = self.store.read_submission(operation_id)
        accepted = self.store.read_accepted(operation_id)
        plan = self.store.read_plan(operation_id)
        if submission is None or accepted is None or plan is None:
            _invalid("CONTROL_PLANE_COMMAND_OPERATION_UNKNOWN")
        request, request_digest, _semantic = submission
        dispatch = self.store.read_dispatch(operation_id)
        if dispatch is None:
            return accepted

        try:
            reconciled = self.executor.reconcile(plan)
        except (BilqisError, MissionControlContractError, OSError):
            reconciled = None
        if reconciled is not None:
            postcondition_ref = self.store.write_postcondition(
                operation_id, reconciled)
            terminal = build_receipt(
                request,
                operation_id=operation_id,
                request_sha256=request_digest,
                state=ActionReceiptState.COMPLETED,
                target_ref=plan.target.ref,
                postcondition_ref=postcondition_ref,
                receipt_refs=(
                    f"command-plan:{plan.digest}",
                    postcondition_ref,
                ),
            )
            self.store.write_terminal(operation_id, terminal)
            return terminal

        worker_result = self.store.read_worker_result(operation_id)
        spawned = self.store.read_spawned(operation_id)
        state = (
            ActionReceiptState.PENDING
            if (
                worker_result is None
                and spawned is not None
                and _pid_live(spawned["pid"])
            )
            else ActionReceiptState.OUTCOME_UNKNOWN
        )
        return build_receipt(
            request,
            operation_id=operation_id,
            request_sha256=request_digest,
            state=state,
            target_ref=plan.target.ref,
        )
