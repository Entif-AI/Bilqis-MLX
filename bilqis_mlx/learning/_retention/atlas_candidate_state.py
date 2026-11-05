"""B12 retained candidate state and B13 custody rehydration."""
from __future__ import annotations

from dataclasses import dataclass, field

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree

from .atlas_candidate_provenance import CandidateCustodyIdentity, CandidateStepProof


STATE_SCHEMA = "bilqis.mlx.candidate-state/provisional-v1"
_RETAINED_STATE_ISSUER = object()


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def is_genesis_allocations(snapshot: MotifAllocationSnapshot) -> bool:
    return (
        type(snapshot) is MotifAllocationSnapshot
        and not snapshot.manifest.slots
        and snapshot.manifest.capacity == INITIAL_MOTIF_CAPACITY
        and not snapshot.observed_uses
        and not snapshot.pending_keys
        and not snapshot.aliases
    )


@dataclass(frozen=True)
class CandidateState:
    """The inseparable retained optimizer, allocation and policy state."""

    optimizer: AdamWStateTree
    policy: PlasticityPolicy
    allocations: MotifAllocationSnapshot
    optimizer_step: int
    custody: CandidateCustodyIdentity | None = None
    step_proofs: tuple = ()
    schema_version: str = STATE_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self):
        if (
            type(self.optimizer) is not AdamWStateTree
            or type(self.policy) is not PlasticityPolicy
            or type(self.allocations) is not MotifAllocationSnapshot
            or type(self.optimizer_step) is not int
            or self.optimizer_step < 0
            or (
                self.custody is not None
                and type(self.custody) is not CandidateCustodyIdentity
            )
            or type(self.step_proofs) is not tuple
            or any(type(proof) is not CandidateStepProof for proof in self.step_proofs)
            or any(
                proof.step_index != index + 1
                for index, proof in enumerate(self.step_proofs)
            )
            or self.schema_version != STATE_SCHEMA
        ):
            _invalid()
        self.optimizer.validate()
        self.policy.validate()
        self.allocations.__post_init__()
        if (
            not is_genesis_allocations(self.allocations)
            and getattr(self, "_issuance", None) is not _RETAINED_STATE_ISSUER
        ):
            _invalid()
        for row in self.policy.row_ages:
            count = self.optimizer.update_counts.get(
                f"identity.bank.{row.bank_index}"
            )
            if count is None or count.ndim != 1 or row.row_index >= count.shape[0]:
                _invalid()


def issue_retained_candidate_state(
    optimizer, policy, allocations, optimizer_step, custody, step_proofs
) -> CandidateState:
    """Issue non-genesis retained state only through the B12 owner path."""
    state = object.__new__(CandidateState)
    for name, value in (
        ("optimizer", optimizer),
        ("policy", policy),
        ("allocations", allocations),
        ("optimizer_step", optimizer_step),
        ("custody", custody),
        ("step_proofs", tuple(step_proofs)),
        ("schema_version", STATE_SCHEMA),
        ("_issuance", _RETAINED_STATE_ISSUER),
    ):
        object.__setattr__(state, name, value)
    state.__post_init__()
    return state


def load_retained_candidate_state_with_parts(
    bundle_root, *, expected_manifest_sha256: str
):
    """Rehydrate retained state only from B13-validated immutable custody."""
    from bilqis_mlx.runtime.bamf_bundle.codec import _load_validated_bundle_parts

    parts = _load_validated_bundle_parts(
        bundle_root, expected_manifest_sha256=expected_manifest_sha256
    )
    proofs = tuple(
        CandidateStepProof.from_record(item)
        for item in parts.records["step_proofs"]["proofs"]
    )
    state = issue_retained_candidate_state(
        parts.numerical,
        parts.policy,
        parts.motif,
        parts.optimizer_step,
        CandidateCustodyIdentity(
            parts.manifest["run_id"],
            parts.manifest["generation"],
            expected_manifest_sha256,
            parts.spec.digest,
            parts.extents.digest,
        ),
        proofs,
    )
    return state, parts
