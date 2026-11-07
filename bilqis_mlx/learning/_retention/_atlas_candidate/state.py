"""Retained candidate state and B13 rehydration."""
from __future__ import annotations
from dataclasses import dataclass, field
import mlx.core as mx
from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from .common import RETAINED_STATE_ISSUER, STATE_SCHEMA, invalid, is_digest
from .proofs import CandidateStepProof

def _is_genesis_allocations(snapshot: MotifAllocationSnapshot) -> bool:
    return (type(snapshot) is MotifAllocationSnapshot
            and not snapshot.manifest.slots
            and snapshot.manifest.capacity == INITIAL_MOTIF_CAPACITY
            and not snapshot.observed_uses and not snapshot.pending_keys
            and not snapshot.aliases)

@dataclass(frozen=True)
class CandidateCustodyIdentity:
    """The published identity of one accepted generation.

    A candidate step may only be authorised against this identity, so
    provenance issued for another run, generation, manifest, topology or
    extents state cannot update this candidate.
    """

    run_id: str
    generation: int
    manifest_sha256: str | None
    topology_digest: str
    extents_digest: str

    def __post_init__(self) -> None:
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or (self.manifest_sha256 is not None
                    and not is_digest(self.manifest_sha256))
                or not is_digest(self.topology_digest)
                or not is_digest(self.extents_digest)):
            invalid()


@dataclass(frozen=True)
class CandidateState:
    """The inseparable proposed optimizer, allocation and policy state."""

    optimizer: AdamWStateTree
    policy: PlasticityPolicy
    allocations: MotifAllocationSnapshot
    optimizer_step: int
    custody: CandidateCustodyIdentity | None = None
    step_proofs: tuple = ()
    schema_version: str = STATE_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self):
        if (type(self.optimizer) is not AdamWStateTree
                or type(self.policy) is not PlasticityPolicy
                or type(self.allocations) is not MotifAllocationSnapshot
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or (self.custody is not None
                    and type(self.custody) is not CandidateCustodyIdentity)
                or type(self.step_proofs) is not tuple
                or any(type(proof) is not CandidateStepProof for proof in self.step_proofs)
                or any(proof.step_index != index + 1
                       for index, proof in enumerate(self.step_proofs))
                or self.schema_version != STATE_SCHEMA):
            invalid()
        self.optimizer.validate()
        self.policy.validate()
        self.allocations.__post_init__()
        if (not _is_genesis_allocations(self.allocations)
                and getattr(self, '_issuance', None) is not RETAINED_STATE_ISSUER):
            invalid()
        for row in self.policy.row_ages:
            count = self.optimizer.update_counts.get(f'identity.bank.{row.bank_index}')
            if count is None or count.ndim != 1 or row.row_index >= count.shape[0]:
                invalid()


def _load_retained_candidate_state_with_parts(
        bundle_root, *, expected_manifest_sha256: str):
    """Rehydrate retained state only from B13-validated immutable custody."""
    from bilqis_mlx.runtime.bamf_bundle.codec import _load_validated_bundle_parts

    parts = _load_validated_bundle_parts(
        bundle_root, expected_manifest_sha256=expected_manifest_sha256)
    proofs = tuple(CandidateStepProof.from_record(item)
                   for item in parts.records["step_proofs"]["proofs"])
    state = object.__new__(CandidateState)
    for name, value in (
            ('optimizer', parts.numerical), ('policy', parts.policy),
            ('allocations', parts.motif), ('optimizer_step', parts.optimizer_step),
            ('custody', CandidateCustodyIdentity(
                parts.manifest['run_id'], parts.manifest['generation'],
                expected_manifest_sha256,
                parts.spec.digest, parts.extents.digest)),
            ('step_proofs', proofs),
            ('schema_version', STATE_SCHEMA),
            ('_issuance', RETAINED_STATE_ISSUER)):
        object.__setattr__(state, name, value)
    state.__post_init__()
    return state, parts
