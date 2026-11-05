"""C14.4 untrusted asynchronous contribution boundary.

Worker signatures authenticate returned bytes and environment identity. They do
not authorize canonical-school mutation. Canonical evaluation and admission are
separate injected authorities so public workers never receive write custody.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
import math
import re
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from bilqis_mlx.errors import ErrorBus, SCHOOL

_MANIFEST_SCHEMA = "bilqis.c14.remote-work-manifest/v1"
_ARTIFACT_SCHEMA = "bilqis.c14.contribution-artifact/v1"
_WORKER_SCHEMA = "bilqis.c14.worker-identity/v1"
_RECEIPT_SCHEMA = "bilqis.c14.worker-receipt/v1"
_EVAL_SCHEMA = "bilqis.c14.independent-evaluation/v1"
_DECISION_SCHEMA = "bilqis.c14.contribution-decision/v1"
_LEDGER_SCHEMA = "bilqis.c14.replay-ledger/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SIG = re.compile(r"[0-9a-f]{128}\Z")
_PUBLIC_KEY = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _text(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def _digest(value: object) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _finite(value: object, *, minimum: float | None = None) -> bool:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        return False
    return minimum is None or float(value) >= minimum


def _canonical_bytes(payload: object) -> bytes:
    return (json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _hash(payload: object) -> str:
    return sha256(_canonical_bytes(payload)).hexdigest()


class ContributionClass(str, Enum):
    EVALUATION = "evaluation"
    CURRICULUM = "curriculum"
    ADAPTER_DELTA = "adapter_delta"
    MOTIF_CANDIDATE = "motif_candidate"
    REGRESSION = "regression"
    DENSE_UPDATE = "dense_update"


class ContributionDisposition(str, Enum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


_EXPECTED_ARTIFACT = {
    ContributionClass.EVALUATION: "evaluation_receipt",
    ContributionClass.CURRICULUM: "curriculum_candidate",
    ContributionClass.ADAPTER_DELTA: "adapter_delta",
    ContributionClass.MOTIF_CANDIDATE: "motif_candidate",
    ContributionClass.REGRESSION: "regression_evidence",
}


@dataclass(frozen=True)
class ResourceBudget:
    max_examples: int
    max_steps: int
    max_seconds: int
    max_bytes: int

    def __post_init__(self) -> None:
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            _invalid("BAMF_C14_RESOURCE_BUDGET_INVALID")


@dataclass(frozen=True)
class AcceptanceContract:
    contract_digest: str
    minimum_score: float
    requires_retention: bool

    def __post_init__(self) -> None:
        if (not _digest(self.contract_digest)
                or not _finite(self.minimum_score)
                or not 0.0 <= float(self.minimum_score) <= 1.0
                or type(self.requires_retention) is not bool):
            _invalid("BAMF_C14_ACCEPTANCE_CONTRACT_INVALID")


@dataclass(frozen=True)
class RemoteWorkManifest:
    manifest_id: str
    retained_generation: str
    source_release: str
    capability_id: str
    seed: int
    partition_id: str
    resource_budget: ResourceBudget
    model_identity: str
    topology_identity: str
    mlx_identity: str
    rights_scope: str
    contribution_class: ContributionClass
    expected_artifact_type: str
    acceptance: AcceptanceContract
    expires_at: int
    replay_id: str
    base_binding_digest: str | None = None
    schema_version: str = field(default=_MANIFEST_SCHEMA, init=False)

    @classmethod
    def create(
        cls, *, manifest_id: str, retained_generation: str,
        source_release: str, capability_id: str, seed: int,
        partition_id: str, resource_budget: ResourceBudget,
        model_identity: str, topology_identity: str, mlx_identity: str,
        rights_scope: str, contribution_class: ContributionClass,
        acceptance: AcceptanceContract, expires_at: int, replay_id: str,
        base_binding_digest: str | None = None,
    ) -> "RemoteWorkManifest":
        if contribution_class is ContributionClass.DENSE_UPDATE:
            _invalid("BAMF_C14_DENSE_UPDATE_AGGREGATION_UNSPECIFIED")
        expected = _EXPECTED_ARTIFACT.get(contribution_class)
        if expected is None:
            _invalid("BAMF_C14_CONTRIBUTION_CLASS_UNSUPPORTED")
        return cls(
            manifest_id, retained_generation, source_release, capability_id,
            seed, partition_id, resource_budget, model_identity,
            topology_identity, mlx_identity, rights_scope,
            contribution_class, expected, acceptance, expires_at,
            replay_id, base_binding_digest,
        )

    def __post_init__(self) -> None:
        if (not all(_text(value) for value in (
                    self.manifest_id, self.capability_id, self.partition_id,
                    self.mlx_identity, self.replay_id))
                or not all(_digest(value) for value in (
                    self.retained_generation, self.source_release,
                    self.model_identity, self.topology_identity))
                or type(self.seed) is not int or self.seed < 0
                or type(self.resource_budget) is not ResourceBudget
                or self.rights_scope != "PUBLIC_FIXTURE"
                or type(self.contribution_class) is not ContributionClass
                or self.contribution_class is ContributionClass.DENSE_UPDATE
                or self.expected_artifact_type
                    != _EXPECTED_ARTIFACT.get(self.contribution_class)
                or type(self.acceptance) is not AcceptanceContract
                or type(self.expires_at) is not int or self.expires_at < 1
                or (self.contribution_class is ContributionClass.ADAPTER_DELTA
                    and not _digest(self.base_binding_digest))
                or (self.contribution_class is not ContributionClass.ADAPTER_DELTA
                    and self.base_binding_digest is not None)
                or self.schema_version != _MANIFEST_SCHEMA):
            _invalid("BAMF_C14_REMOTE_WORK_MANIFEST_INVALID")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "retained_generation": self.retained_generation,
            "source_release": self.source_release,
            "capability_id": self.capability_id,
            "seed": self.seed,
            "partition_id": self.partition_id,
            "resource_budget": asdict(self.resource_budget),
            "model_identity": self.model_identity,
            "topology_identity": self.topology_identity,
            "mlx_identity": self.mlx_identity,
            "rights_scope": self.rights_scope,
            "contribution_class": self.contribution_class.value,
            "expected_artifact_type": self.expected_artifact_type,
            "acceptance": asdict(self.acceptance),
            "expires_at": self.expires_at,
            "replay_id": self.replay_id,
            "base_binding_digest": self.base_binding_digest,
        }

    @property
    def digest(self) -> str:
        self.__post_init__()
        return _hash(self.canonical_payload())


@dataclass(frozen=True)
class EnvironmentIdentity:
    hardware: str
    os: str
    mlx_version: str
    backend: str
    device_count: int

    def __post_init__(self) -> None:
        if (not all(_text(value) for value in (
                    self.hardware, self.os, self.mlx_version, self.backend))
                or type(self.device_count) is not int or self.device_count < 1):
            _invalid("BAMF_C14_ENVIRONMENT_IDENTITY_INVALID")

    @property
    def digest(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True)
class WorkerIdentity:
    worker_id: str
    public_key_hex: str
    environment: EnvironmentIdentity
    schema_version: str = field(default=_WORKER_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (not _text(self.worker_id)
                or not isinstance(self.public_key_hex, str)
                or _PUBLIC_KEY.fullmatch(self.public_key_hex) is None
                or type(self.environment) is not EnvironmentIdentity
                or self.schema_version != _WORKER_SCHEMA):
            _invalid("BAMF_C14_WORKER_IDENTITY_INVALID")


@dataclass(frozen=True)
class ContributionArtifact:
    artifact_type: str
    payload: bytes
    base_binding_digest: str | None = None
    affected_parameter_ids: tuple[str, ...] = ()
    schema_version: str = field(default=_ARTIFACT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (not _text(self.artifact_type)
                or type(self.payload) is not bytes or not self.payload
                or (self.base_binding_digest is not None
                    and not _digest(self.base_binding_digest))
                or type(self.affected_parameter_ids) is not tuple
                or any(not _text(item) for item in self.affected_parameter_ids)
                or self.affected_parameter_ids
                    != tuple(sorted(set(self.affected_parameter_ids)))
                or self.schema_version != _ARTIFACT_SCHEMA):
            _invalid("BAMF_C14_CONTRIBUTION_ARTIFACT_INVALID")

    @property
    def digest(self) -> str:
        return sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class WorkerReceipt:
    manifest_digest: str
    worker: WorkerIdentity
    artifact: ContributionArtifact
    claimed_score: float
    completed_at: int
    signature_hex: str
    schema_version: str = field(default=_RECEIPT_SCHEMA, init=False)

    @classmethod
    def unsigned(
        cls, *, manifest: RemoteWorkManifest, worker: WorkerIdentity,
        artifact: ContributionArtifact, claimed_score: float,
        completed_at: int,
    ) -> "WorkerReceipt":
        return cls(
            manifest.digest, worker, artifact, claimed_score,
            completed_at, "0" * 128,
        )

    def __post_init__(self) -> None:
        if (not _digest(self.manifest_digest)
                or type(self.worker) is not WorkerIdentity
                or type(self.artifact) is not ContributionArtifact
                or not _finite(self.claimed_score)
                or not 0.0 <= float(self.claimed_score) <= 1.0
                or type(self.completed_at) is not int or self.completed_at < 0
                or not isinstance(self.signature_hex, str)
                or _SIG.fullmatch(self.signature_hex) is None
                or self.schema_version != _RECEIPT_SCHEMA):
            _invalid("BAMF_C14_WORKER_RECEIPT_INVALID")

    def signing_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "manifest_digest": self.manifest_digest,
            "worker": {
                "worker_id": self.worker.worker_id,
                "public_key_hex": self.worker.public_key_hex,
                "environment": asdict(self.worker.environment),
                "schema_version": self.worker.schema_version,
            },
            "artifact": {
                "artifact_type": self.artifact.artifact_type,
                "digest": self.artifact.digest,
                "base_binding_digest": self.artifact.base_binding_digest,
                "affected_parameter_ids": self.artifact.affected_parameter_ids,
                "schema_version": self.artifact.schema_version,
            },
            "claimed_score": self.claimed_score,
            "completed_at": self.completed_at,
        }

    def signing_bytes(self) -> bytes:
        return _canonical_bytes(self.signing_payload())

    def with_signature(self, signature_hex: str) -> "WorkerReceipt":
        return WorkerReceipt(
            self.manifest_digest, self.worker, self.artifact,
            self.claimed_score, self.completed_at, signature_hex,
        )

    @property
    def digest(self) -> str:
        return _hash({**self.signing_payload(), "signature_hex": self.signature_hex})


@dataclass(frozen=True)
class ReplayLedger:
    consumed_replay_ids: tuple[str, ...] = ()
    schema_version: str = field(default=_LEDGER_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (type(self.consumed_replay_ids) is not tuple
                or any(not _text(item) for item in self.consumed_replay_ids)
                or self.consumed_replay_ids
                    != tuple(sorted(set(self.consumed_replay_ids)))
                or self.schema_version != _LEDGER_SCHEMA):
            _invalid("BAMF_C14_REPLAY_LEDGER_INVALID")

    def consume(self, replay_id: str) -> "ReplayLedger":
        self.__post_init__()
        if replay_id in self.consumed_replay_ids:
            _invalid("BAMF_C14_CONTRIBUTION_REPLAYED")
        return ReplayLedger(tuple(sorted((*self.consumed_replay_ids, replay_id))))


@dataclass(frozen=True)
class VerifiedRemoteReceipt:
    receipt_digest: str
    replay_ledger: ReplayLedger


@dataclass(frozen=True)
class IndependentEvaluation:
    passed: bool
    score: float
    evidence_digest: str
    retention_outcome: str
    schema_version: str = field(default=_EVAL_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (type(self.passed) is not bool
                or not _finite(self.score)
                or not 0.0 <= float(self.score) <= 1.0
                or not _digest(self.evidence_digest)
                or not _text(self.retention_outcome)
                or self.schema_version != _EVAL_SCHEMA):
            _invalid("BAMF_C14_INDEPENDENT_EVALUATION_INVALID")


@dataclass(frozen=True)
class ContributionDecision:
    disposition: ContributionDisposition
    manifest_digest: str
    receipt_digest: str
    independent_score: float
    independent_evidence_digest: str
    retention_outcome: str
    replay_ledger: ReplayLedger
    schema_version: str = field(default=_DECISION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (type(self.disposition) is not ContributionDisposition
                or not _digest(self.manifest_digest)
                or not _digest(self.receipt_digest)
                or not _finite(self.independent_score)
                or not _digest(self.independent_evidence_digest)
                or not _text(self.retention_outcome)
                or type(self.replay_ledger) is not ReplayLedger
                or self.schema_version != _DECISION_SCHEMA):
            _invalid("BAMF_C14_CONTRIBUTION_DECISION_INVALID")


def _verify_signature(receipt: WorkerReceipt) -> None:
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(receipt.worker.public_key_hex)
        ).verify(bytes.fromhex(receipt.signature_hex), receipt.signing_bytes())
    except (ValueError, InvalidSignature):
        _invalid("BAMF_C14_WORKER_SIGNATURE_INVALID")


def verify_remote_receipt(
    manifest: RemoteWorkManifest,
    receipt: WorkerReceipt,
    *, now: int,
    replay_ledger: ReplayLedger,
) -> VerifiedRemoteReceipt:
    """Authenticate worker result and prove it belongs to this frozen assignment."""
    if (type(manifest) is not RemoteWorkManifest
            or type(receipt) is not WorkerReceipt
            or type(now) is not int or now < 0
            or type(replay_ledger) is not ReplayLedger):
        _invalid("BAMF_C14_REMOTE_VERIFY_INPUT_INVALID")
    manifest.__post_init__()
    receipt.__post_init__()
    replay_ledger.__post_init__()
    if now > manifest.expires_at or receipt.completed_at > manifest.expires_at:
        _invalid("BAMF_C14_REMOTE_WORK_EXPIRED")
    if receipt.manifest_digest != manifest.digest:
        _invalid("BAMF_C14_REMOTE_MANIFEST_MISMATCH")
    if receipt.artifact.artifact_type != manifest.expected_artifact_type:
        _invalid("BAMF_C14_REMOTE_ARTIFACT_TYPE_MISMATCH")
    if len(receipt.artifact.payload) > manifest.resource_budget.max_bytes:
        _invalid("BAMF_C14_REMOTE_ARTIFACT_BUDGET_EXCEEDED")
    if manifest.contribution_class is ContributionClass.ADAPTER_DELTA:
        if (receipt.artifact.base_binding_digest != manifest.base_binding_digest
                or not receipt.artifact.affected_parameter_ids):
            _invalid("BAMF_C14_REMOTE_DELTA_BINDING_MISMATCH")
    elif receipt.artifact.base_binding_digest is not None or receipt.artifact.affected_parameter_ids:
        _invalid("BAMF_C14_REMOTE_ARTIFACT_SCOPE_INVALID")
    _verify_signature(receipt)
    return VerifiedRemoteReceipt(
        receipt.digest, replay_ledger.consume(manifest.replay_id))


def admit_remote_contribution(
    manifest: RemoteWorkManifest,
    receipt: WorkerReceipt,
    *, now: int,
    replay_ledger: ReplayLedger,
    independent_evaluator: Callable[[RemoteWorkManifest, WorkerReceipt], IndependentEvaluation],
    canonical_admitter: Callable[[RemoteWorkManifest, WorkerReceipt, IndependentEvaluation], object],
) -> ContributionDecision:
    """Independent canonical evaluation owns admission; worker score is ignored."""
    if not callable(independent_evaluator) or not callable(canonical_admitter):
        _invalid("BAMF_C14_ADMISSION_AUTHORITY_INVALID")
    verified = verify_remote_receipt(
        manifest, receipt, now=now, replay_ledger=replay_ledger)
    evaluation = independent_evaluator(manifest, receipt)
    if type(evaluation) is not IndependentEvaluation:
        _invalid("BAMF_C14_INDEPENDENT_EVALUATION_REQUIRED")
    evaluation.__post_init__()
    passes = (evaluation.passed
              and evaluation.score >= manifest.acceptance.minimum_score
              and (not manifest.acceptance.requires_retention
                   or evaluation.retention_outcome == "retention:pass"))
    disposition = (
        ContributionDisposition.ADMITTED if passes
        else ContributionDisposition.REJECTED)
    if passes:
        canonical_admitter(manifest, receipt, evaluation)
    return ContributionDecision(
        disposition, manifest.digest, verified.receipt_digest,
        evaluation.score, evaluation.evidence_digest,
        evaluation.retention_outcome, verified.replay_ledger,
    )


def dispatch_eligible_work(
    manifests: tuple[RemoteWorkManifest, ...], *,
    available_workers: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    """Optional dispatch only; empty swarm never blocks local canonical work."""
    if (type(manifests) is not tuple
            or any(type(item) is not RemoteWorkManifest for item in manifests)
            or type(available_workers) is not tuple
            or any(not _text(worker) for worker in available_workers)):
        _invalid("BAMF_C14_DISPATCH_INPUT_INVALID")
    if not available_workers:
        return ()
    workers = tuple(sorted(set(available_workers)))
    ordered = tuple(sorted(manifests, key=lambda item: item.digest))
    return tuple(
        (workers[index % len(workers)], manifest.digest)
        for index, manifest in enumerate(ordered)
    )
