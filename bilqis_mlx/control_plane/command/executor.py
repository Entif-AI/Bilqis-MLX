"""CP05 adapter that delegates BAMF behavior to the accepted C11 CLI."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path
import subprocess
import sys

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control.operator import OperatorActionRequestV2
from bilqis_mlx.runtime.bamf_bundle import inspect_accepted_generation

from .c11 import (
    parameter_flags, parameter_map, report_target, run_cli_json, same_lineage,
)
from .model import (
    CommandAction, CommandMode, CommandPlan, ResolvedCommandTarget,
    intent_sha256, request_sha256,
)
from ..transport import _invalid

class C11CommandExecutor:
    """Preflight and execute only through the existing human operator boundary."""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir).expanduser().resolve()

    def _resume_preflight(self, request: OperatorActionRequestV2) -> tuple[dict, tuple[str, ...]]:
        omit = frozenset({"atlas_admission_scope", "admission_policy"})
        argv = (
            "train", "--dry-run", "--resume", "--run-dir", str(self.run_dir),
            *parameter_flags(request.parameters, omit=omit),
        )
        return run_cli_json(tuple(argv)), tuple(argv)

    def _create_preflight(self, request: OperatorActionRequestV2) -> tuple[dict, tuple[str, ...]]:
        omit = frozenset({"atlas_admission_scope", "admission_policy"})
        argv = (
            "train", "--dry-run", "--run-dir", str(self.run_dir),
            *parameter_flags(request.parameters, omit=omit),
        )
        return run_cli_json(tuple(argv)), tuple(argv)

    def _validate_admission_scope(
        self, request: OperatorActionRequestV2, target: ResolvedCommandTarget,
    ) -> None:
        parameters = parameter_map(request.parameters)
        scope = parameters.get("atlas_admission_scope")
        if not isinstance(scope, str) or not scope:
            _invalid("CONTROL_PLANE_COMMAND_ADMISSION_SCOPE_REQUIRED")
        from bilqis_mlx.runtime.atlas_admission import read_atlas_enrollment_request_v2
        enrollment = read_atlas_enrollment_request_v2(Path(scope))
        if (enrollment.requested_run_id != target.run_id
                or enrollment.requested_run_seed != target.run_seed
                or enrollment.requested_topology_digest != target.topology_sha256
                or enrollment.source_approval.atlas_release_sha256
                != target.semantic_release_sha256):
            _invalid("CONTROL_PLANE_COMMAND_ADMISSION_TARGET_CONFLICT")

    @staticmethod
    def _action(request: OperatorActionRequestV2) -> CommandAction:
        try:
            action = CommandAction(request.action)
        except ValueError:
            _invalid("CONTROL_PLANE_COMMAND_ACTION_UNSUPPORTED")
        if action in {CommandAction.PAUSE, CommandAction.STOP}:
            _invalid("CONTROL_PLANE_COMMAND_ACTION_UNAVAILABLE")
        return action

    @staticmethod
    def _validate_parameters(action: CommandAction, parameters: dict) -> None:
        admission_keys = {"atlas_admission_scope", "admission_policy"}
        if action is CommandAction.ADMISSION_LEASE:
            if set(parameters) - admission_keys:
                _invalid("CONTROL_PLANE_COMMAND_PARAMETER_UNSUPPORTED")
            policy = parameters.get("admission_policy")
            if policy is not None and policy != "atlas-release":
                _invalid("CONTROL_PLANE_COMMAND_ADMISSION_POLICY_INVALID")
            return
        if set(parameters) & admission_keys:
            _invalid("CONTROL_PLANE_COMMAND_ADMISSION_ACTION_REQUIRED")
        if (
            action in {CommandAction.STATUS, CommandAction.CHECKPOINT_VERIFY}
            and parameters
        ):
            _invalid("CONTROL_PLANE_COMMAND_PARAMETER_UNSUPPORTED")

    @staticmethod
    def _runtime_argv(dry_argv: tuple[str, ...], dry_run: bool) -> list[str]:
        actual = list(dry_argv)
        if not dry_run:
            actual.remove("--dry-run")
            actual.append("--human-run")
        return actual

    def _create_parts(self, request: OperatorActionRequestV2):
        report, dry_argv = self._create_preflight(request)
        target = report_target(self.run_dir, report, existing=False)
        mode = CommandMode.DRY_RUN if request.dry_run else CommandMode.MUTATING
        postcondition = (
            "create-preview" if request.dry_run else "accepted-generation")
        return report, target, mode, self._runtime_argv(
            dry_argv, request.dry_run), postcondition

    def _existing_parts(
        self, request: OperatorActionRequestV2, action: CommandAction,
        parameters: dict,
    ):
        report, dry_argv = self._resume_preflight(request)
        target = report_target(self.run_dir, report, existing=True)
        if action is CommandAction.STATUS:
            return report, target, CommandMode.READ_ONLY, [], "operator-status"
        if action is CommandAction.CHECKPOINT_VERIFY:
            return report, target, CommandMode.READ_ONLY, [], "checkpoint-verified"
        if action is CommandAction.ADMISSION_LEASE:
            return self._admission_parts(request, report, target, parameters)
        mode = CommandMode.DRY_RUN if request.dry_run else CommandMode.MUTATING
        postcondition = (
            "resume-preview" if request.dry_run else "operator-run-completed")
        return report, target, mode, self._runtime_argv(
            dry_argv, request.dry_run), postcondition

    def _admission_parts(self, request, report, target, parameters):
        if request.dry_run:
            _invalid("CONTROL_PLANE_COMMAND_ADMISSION_DRY_RUN_UNAVAILABLE")
        self._validate_admission_scope(request, target)
        scope = parameters["atlas_admission_scope"]
        actual = [
            "train", "--human-run", "--resume", "--run-dir", str(self.run_dir),
            "--admission-policy", "atlas-release",
            "--atlas-admission-scope", str(scope),
        ]
        return report, target, CommandMode.MUTATING, actual, "admission-lease"

    def _preflight(
        self, request: OperatorActionRequestV2, operation_id: str, *,
        require_authorization: bool,
    ) -> tuple[CommandPlan, dict]:
        action = self._action(request)
        parameters = parameter_map(request.parameters)
        self._validate_parameters(action, parameters)
        if action is CommandAction.CREATE:
            parts = self._create_parts(request)
        else:
            parts = self._existing_parts(request, action, parameters)
        report, target, mode, actual, postcondition = parts
        if require_authorization and mode is CommandMode.MUTATING and not request.human_authorized:
            _invalid("CONTROL_PLANE_COMMAND_HUMAN_AUTHORIZATION_REQUIRED")
        plan = CommandPlan(
            operation_id=operation_id,
            request_sha256=request_sha256(request),
            intent_sha256=intent_sha256(request),
            action=action,
            mode=mode,
            target=target,
            argv=tuple(actual),
            postcondition_kind=postcondition,
        )
        return plan, {
            "kind": "preflight",
            "action": action.value,
            "mode": mode.value,
            "target": target.to_record(),
            "c11_report": report,
        }

    def preview(
        self, request: OperatorActionRequestV2, operation_id: str,
    ) -> tuple[CommandPlan, dict]:
        """Resolve an exact plan without treating preview as human authorization."""
        return self._preflight(
            request, operation_id, require_authorization=False)

    def preflight(
        self, request: OperatorActionRequestV2, operation_id: str,
    ) -> tuple[CommandPlan, dict]:
        return self._preflight(
            request, operation_id, require_authorization=True)

    def inert_postcondition(
        self, plan: CommandPlan, preflight: dict,
    ) -> dict:
        if plan.mode is CommandMode.MUTATING:
            _invalid("CONTROL_PLANE_COMMAND_MUTATION_REQUIRED")
        if plan.action is CommandAction.STATUS:
            from bilqis_mlx.presentation.operator_cli.inspection import _inspect
            return {
                "kind": "operator-status",
                "target": plan.target.to_record(),
                "status": _inspect(self.run_dir),
            }
        if plan.action is CommandAction.CHECKPOINT_VERIFY:
            inspection = inspect_accepted_generation(self.run_dir / "bamf-state.json")
            if inspection is None:
                _invalid("CONTROL_PLANE_COMMAND_CHECKPOINT_UNAVAILABLE")
            return {
                "kind": "checkpoint-verified",
                "target": plan.target.to_record(),
                "inspection": asdict(inspection),
            }
        return preflight

    def execute(
        self, plan: CommandPlan, *, stdout_path: Path, stderr_path: Path,
    ) -> tuple[int | None, str | None]:
        if not plan.requires_worker:
            _invalid("CONTROL_PLANE_COMMAND_WORKER_NOT_REQUIRED")
        try:
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                completed = subprocess.run(
                    [sys.executable, "-m", "bilqis_mlx.cli", *plan.argv],
                    stdout=stdout, stderr=stderr, check=False,
                )
        except OSError as error:
            digest = hashlib.sha256(
                f"{type(error).__name__}:{error}".encode("utf-8")).hexdigest()
            return None, f"command-error:spawn:{digest}"
        if completed.returncode != 0:
            digest = hashlib.sha256(stderr_path.read_bytes()).hexdigest()
            return completed.returncode, (
                f"command-error:{completed.returncode}:{digest}")
        return 0, None

    def _current_target(self) -> ResolvedCommandTarget | None:
        try:
            report = run_cli_json((
                "train", "--dry-run", "--resume", "--run-dir", str(self.run_dir)))
            return report_target(self.run_dir, report, existing=True)
        except (BilqisError, OSError):
            return None

    def verify_target_before_execute(self, plan: CommandPlan) -> None:
        """Fail closed if authority changed after durable ACCEPTED."""
        if plan.action is CommandAction.CREATE:
            if (self.run_dir / "bamf-state.json").exists():
                _invalid("CONTROL_PLANE_COMMAND_TARGET_DRIFT")
            dry_argv = tuple(
                "--dry-run" if item == "--human-run" else item
                for item in plan.argv
            )
            report = run_cli_json(dry_argv)
            current = report_target(self.run_dir, report, existing=False)
        else:
            current = self._current_target()
        if current is None or current != plan.target:
            _invalid("CONTROL_PLANE_COMMAND_TARGET_DRIFT")

    def postcondition_after_success(self, plan: CommandPlan) -> dict:
        current = self._current_target()
        if current is None or not same_lineage(plan.target, current):
            _invalid("CONTROL_PLANE_COMMAND_POSTCONDITION_UNVERIFIED")
        result = {
            "kind": plan.postcondition_kind,
            "before": plan.target.to_record(),
            "after": current.to_record(),
            "cli_exit": 0,
        }
        if plan.action is CommandAction.ADMISSION_LEASE:
            from bilqis_mlx.runtime.atlas_lease_storage import classify_accepted_atlas_epoch
            result["admission_epoch"] = classify_accepted_atlas_epoch(self.run_dir)
            if result["admission_epoch"] == "staged":
                _invalid("CONTROL_PLANE_COMMAND_POSTCONDITION_UNVERIFIED")
        return result

    def reconcile(self, plan: CommandPlan) -> dict | None:
        """Read authoritative state only; never relaunch an admitted operation."""
        current = self._current_target()
        if current is None or not same_lineage(plan.target, current):
            return None
        if plan.action is CommandAction.CREATE:
            return {
                "kind": "reconciled-create",
                "before": plan.target.to_record(),
                "after": current.to_record(),
            }
        if plan.action is CommandAction.ADMISSION_LEASE:
            from bilqis_mlx.runtime.atlas_lease_storage import classify_accepted_atlas_epoch
            epoch = classify_accepted_atlas_epoch(self.run_dir)
            if epoch != "staged":
                return {
                    "kind": "reconciled-admission",
                    "before": plan.target.to_record(),
                    "after": current.to_record(),
                    "admission_epoch": epoch,
                }
            return None
        if plan.action in {CommandAction.RESUME, CommandAction.OWNER_LAUNCH}:
            if (
                current.generation is not None
                and plan.target.generation is not None
                and current.optimizer_step is not None
                and plan.target.optimizer_step is not None
                and (
                    current.generation > plan.target.generation
                    or current.optimizer_step > plan.target.optimizer_step
                )
            ):
                return {
                    "kind": "reconciled-progress",
                    "before": plan.target.to_record(),
                    "after": current.to_record(),
                }
        return None
