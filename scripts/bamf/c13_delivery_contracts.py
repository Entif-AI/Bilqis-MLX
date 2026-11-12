"""Immutable contracts for the C13.1 disposable integrated witness."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.executable_release import ExecutableFactoryRelease
from bilqis_mlx.runtime.bamf_first_student import BamfFoundationConfig, LaunchReceipt

CONFIG_SCHEMA = "bilqis.c13.delivery-config/v1"
FOUNDATION_SCHEMA = "bilqis.c13.foundation-launch-input/v1"
SOURCE_SCHEMA = "bilqis.c13.episode-source-release/v1"
CASE_SCHEMA = "bilqis.c13.episode-binding-case/v1"
RECEIPT_SCHEMA = "bilqis.c13.delivery-receipt/v1"
SEMANTIC_DELTA_SCHEMA = "bilqis.c13.semantic-delta-receipt/v1"
MAX_STEPS = 64
ACTORS = ("A", "B", "C")


def fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


@dataclass(frozen=True)
class DeliveryConfig:
    baseline_seeds: tuple[int, ...] = tuple(range(64))
    fresh_seeds: tuple[int, ...] = tuple(range(64, 128))
    depths: tuple[int, ...] = (1, 2, 3, 4)
    schema_version: str = CONFIG_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != CONFIG_SCHEMA
                or self.baseline_seeds != tuple(range(64))
                or self.fresh_seeds != tuple(range(64, 128))
                or self.depths != (1, 2, 3, 4)):
            fail("BAMF_C13_DELIVERY_CONFIG_INVALID")


@dataclass(frozen=True)
class FoundationLaunchInput:
    config: BamfFoundationConfig
    admitted_release: ExecutableFactoryRelease
    schema_version: str = FOUNDATION_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != FOUNDATION_SCHEMA
                or type(self.config) is not BamfFoundationConfig
                or type(self.admitted_release) is not ExecutableFactoryRelease):
            fail("BAMF_C13_FOUNDATION_INPUT_INVALID")
        self.config.validate()


@dataclass(frozen=True)
class EpisodeSourceRelease:
    release_sha256: str
    semantic_release: str
    foundation: FoundationLaunchInput | None = None
    source_family_id: str = "bamf.c13.episode-binding/v1"
    schema_version: str = SOURCE_SCHEMA

    def __post_init__(self) -> None:
        values = (self.release_sha256, self.semantic_release)
        if (self.schema_version != SOURCE_SCHEMA
                or any(not isinstance(value, str) or len(value) != 64
                       or any(char not in "0123456789abcdef" for char in value)
                       for value in values)
                or (self.foundation is not None
                    and (type(self.foundation) is not FoundationLaunchInput
                         or self.foundation.admitted_release.release_sha256
                         != self.release_sha256))
                or not self.source_family_id):
            fail("BAMF_C13_SOURCE_RELEASE_INVALID")


@dataclass(frozen=True)
class CandidateAttemptReceipt:
    outcome: str
    parent_generation: int
    current_generation: int
    parent_optimizer_step: int
    current_optimizer_step: int
    parent_candidate_sha256: str
    current_candidate_sha256: str
    attempted_steps: int

    def __post_init__(self) -> None:
        attempted = self.outcome in ("ACCEPTED", "REJECTED")
        if (self.outcome not in ("ACCEPTED", "REJECTED", "HELD", "ACTION_REQUIRED")
                or self.attempted_steps != int(attempted)):
            fail("BAMF_C13_CANDIDATE_ATTEMPT_INVALID")
        if self.outcome == "ACCEPTED" and (
                self.current_generation != self.parent_generation + 1
                or self.current_optimizer_step <= self.parent_optimizer_step
                or self.current_candidate_sha256 == self.parent_candidate_sha256):
            fail("BAMF_C13_ACCEPTED_CANDIDATE_DRIFT")
        if self.outcome != "ACCEPTED" and (
                self.current_generation != self.parent_generation
                or self.current_optimizer_step != self.parent_optimizer_step
                or self.current_candidate_sha256 != self.parent_candidate_sha256):
            fail("BAMF_C13_NONACCEPTED_PARENT_DRIFT")


@dataclass(frozen=True)
class SemanticDeltaReceipt:
    semantic_id: str
    parent_generation: int
    current_generation: int
    optimizer_step: int
    prior_state_preserved: bool
    new_rows: tuple[tuple[int, int], ...]
    schema_version: str = SEMANTIC_DELTA_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != SEMANTIC_DELTA_SCHEMA
                or not self.semantic_id
                or self.current_generation != self.parent_generation + 1
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or self.prior_state_preserved is not True
                or not self.new_rows
                or any(type(bank) is not int or type(row) is not int
                       or bank < 0 or row < 0 for bank, row in self.new_rows)):
            fail("BAMF_C13_SEMANTIC_DELTA_RECEIPT_INVALID")


@dataclass(frozen=True)
class DeliveryReceipt:
    source_release_sha256: str
    semantic_release: str
    fixture_manifest_sha256: str
    baseline_case_count: int
    fresh_case_count: int
    max_steps: int
    status: str
    exercised_behaviors: tuple[str, ...]
    remaining_behaviors: tuple[str, ...]
    launch_receipt: LaunchReceipt | None = None
    run_dir: str | None = None
    candidate_attempts: tuple[CandidateAttemptReceipt, ...] = ()
    semantic_delta: SemanticDeltaReceipt | None = None
    schema_version: str = RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != RECEIPT_SCHEMA
                or self.status not in (
                    "PREPARED", "FOUNDATION_CREATED", "CANDIDATE_EXERCISED", "EXECUTED")
                or self.baseline_case_count != 64 or self.fresh_case_count != 64
                or not 0 <= self.max_steps <= MAX_STEPS
                or len(self.fixture_manifest_sha256) != 64
                or not isinstance(self.candidate_attempts, tuple)
                or any(type(item) is not CandidateAttemptReceipt
                       for item in self.candidate_attempts)
                or (self.semantic_delta is not None
                    and type(self.semantic_delta) is not SemanticDeltaReceipt)):
            fail("BAMF_C13_DELIVERY_RECEIPT_INVALID")
        has_launch = type(self.launch_receipt) is LaunchReceipt
        if self.status == "PREPARED":
            if (has_launch or self.run_dir is not None or self.candidate_attempts
                    or self.semantic_delta is not None):
                fail("BAMF_C13_DELIVERY_RECEIPT_INVALID")
            return
        if (not has_launch or not isinstance(self.run_dir, str) or not self.run_dir
                or self.launch_receipt.factory_release_sha256
                != self.source_release_sha256):
            fail("BAMF_C13_DELIVERY_RECEIPT_INVALID")


__all__ = (
    "ACTORS", "CASE_SCHEMA", "CandidateAttemptReceipt", "DeliveryConfig",
    "DeliveryReceipt", "EpisodeSourceRelease", "FoundationLaunchInput",
    "MAX_STEPS", "SemanticDeltaReceipt", "fail",
)
