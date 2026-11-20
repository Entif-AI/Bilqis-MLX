"""Grade-neutral #1334 certification state machine over injected measurement."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from bilqis_mlx.errors import BilqisError, ErrorBus, SCHOOL

from .grade_certification_contracts import (
    AcceptedGradeCertificationReceipt,
    CertificationObligationScore,
    CertificationOutcome,
    GradeCertificationPolicy,
    GradeCertificationRequest,
    _issue_success_receipt,
)
from .grade_certification_custody import (
    load_certification_attempt,
    load_certification_receipt,
    load_certification_request,
    supersede_certification_attempt,
)
from .grade_certification_custody_common import _root


def _invalid(reason: str):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


def _sha(value: object) -> bool:
    return (
        type(value) is str and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


@dataclass(frozen=True)
class CertificationMeasurement:
    cohort_sha256: str
    scores: tuple[CertificationObligationScore, ...]

    def __post_init__(self) -> None:
        if (
            not _sha(self.cohort_sha256)
            or type(self.scores) is not tuple
            or not self.scores
            or any(type(item) is not CertificationObligationScore
                   for item in self.scores)
            or len({(item.owner, item.obligation_key)
                    for item in self.scores}) != len(self.scores)
        ):
            _invalid("BAMF_GRADE_CERTIFICATION_MEASUREMENT_INVALID")


@dataclass(frozen=True)
class CertificationExecutionResult:
    status: str
    request_sha256: str
    receipt: AcceptedGradeCertificationReceipt | None = None
    blockers: tuple[CertificationObligationScore, ...] = ()
    supersession_reason: str | None = None


def _attempt_path(run_dir: Path, request: GradeCertificationRequest) -> Path:
    return (
        Path(run_dir) / "grade-certification" / "attempts"
        / request.attempt_sha256 / "attempt.json"
    )


def _trigger_matches_request(
    request: GradeCertificationRequest,
    measurement: CertificationMeasurement,
) -> bool:
    expected = {
        *[("ACTIVE", item) for item in request.active_obligations],
        *[("PROTECTED", item) for item in request.protected_obligations],
    }
    actual = {(item.owner, item.obligation_key) for item in measurement.scores}
    return expected == actual and len(actual) == len(measurement.scores)


def _blockers(request, scores) -> tuple[CertificationObligationScore, ...]:
    baselines = {
        item.obligation_key: item for item in request.protected_baselines
    }
    result = []
    for item in scores:
        if item.owner == "ACTIVE" and item.correct != item.total:
            result.append(item)
        elif item.owner == "PROTECTED":
            baseline = baselines.get(item.obligation_key)
            if baseline is None:
                continue
            if (
                item.correct * baseline.total
                < baseline.correct * item.total
            ):
                result.append(item)
    return tuple(result)


def _replace_active(
    scores: tuple[CertificationObligationScore, ...],
    replacement: CertificationObligationScore,
) -> tuple[CertificationObligationScore, ...]:
    found = False
    result = []
    for item in scores:
        if (
            item.owner == "ACTIVE"
            and item.obligation_key == replacement.obligation_key
        ):
            result.append(replacement)
            found = True
        else:
            result.append(item)
    if not found:
        _invalid("BAMF_GRADE_CERTIFICATION_REPLACEMENT_SCOPE_INVALID")
    return tuple(result)


def _terminal_result(run_dir: Path, view) -> CertificationExecutionResult:
    receipt = (
        load_certification_receipt(run_dir, view.receipt_sha256)
        if view.status == "SUCCEEDED" and view.receipt_sha256 is not None
        else None
    )
    return CertificationExecutionResult(
        view.status,
        view.request.request_sha256,
        receipt=receipt,
        blockers=view.blockers,
        supersession_reason=view.supersession_reason,
    )


def _current_or_supersede(
    run_dir: Path,
    request: GradeCertificationRequest,
    require_current: Callable[[], GradeCertificationRequest],
):
    try:
        current = require_current()
        if (
            type(current) is not GradeCertificationRequest
            or current.request_sha256 != request.request_sha256
        ):
            _invalid("BAMF_GRADE_CERTIFICATION_CURRENTNESS_DRIFT")
        return current, None
    except BilqisError as error:
        reason = error.context.get("reason")
        superseding_reasons = {
            "BAMF_GRADE_CERTIFICATION_CURRENTNESS_DRIFT",
            "BAMF_GRADE_CERTIFICATION_POLICY_SELECTION_DRIFT",
            "BAMF_GRADE_CERTIFICATION_REQUEST_REISSUE_DRIFT",
        }
        if reason not in superseding_reasons:
            raise
        view = supersede_certification_attempt(
            run_dir, request, reason=reason)
        return None, _terminal_result(run_dir, view)


def _supersede_stale_running_attempts(root, request) -> None:
    attempts = _root(root) / "attempts"
    if not attempts.exists():
        return
    if attempts.is_symlink() or not attempts.is_dir():
        _invalid("BAMF_GRADE_CERTIFICATION_CUSTODY_UNSAFE")
    for path in sorted(attempts.iterdir(), key=lambda item: item.name):
        if path.is_symlink() or not path.is_dir():
            _invalid("BAMF_GRADE_CERTIFICATION_CUSTODY_UNSAFE")
        if path.name == request.attempt_sha256:
            continue
        terminal = path / "terminal.json"
        if terminal.is_symlink():
            _invalid("BAMF_GRADE_CERTIFICATION_CUSTODY_UNSAFE")
        if terminal.exists():
            continue
        stale_request = load_certification_request(root, path.name)
        stale = load_certification_attempt(root, stale_request)
        if stale.status == "RUNNING":
            supersede_certification_attempt(
                root, stale_request,
                reason="BAMF_GRADE_CERTIFICATION_CURRENTNESS_DRIFT")
