"""Public B12.2 candidate custody surface."""
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree

from ._atlas_candidate.common import LEGACY_STEP_PROOF_SCHEMA, STEP_PROOF_SCHEMA
from ._atlas_candidate.proofs import CandidateStepProof
from ._atlas_candidate.state import (
    CandidateCustodyIdentity, CandidateState,
    _issue_parameter_extension_state,
    _load_retained_candidate_state_with_parts,
)
from ._atlas_candidate.transaction import (
    CandidateTransaction, begin_candidate, candidate_step, resolve_candidate,
)


def issue_parameter_extension_state(
        parent: CandidateState, optimizer: AdamWStateTree,
        policy: PlasticityPolicy) -> CandidateState:
    """Public B12 owner seam for a staged non-training parameter extension."""
    return _issue_parameter_extension_state(parent, optimizer, policy)

__all__ = (
    "CandidateCustodyIdentity", "CandidateState", "CandidateStepProof",
    "CandidateTransaction", "LEGACY_STEP_PROOF_SCHEMA", "STEP_PROOF_SCHEMA",
    "begin_candidate", "candidate_step", "resolve_candidate",
    "issue_parameter_extension_state",
    "_load_retained_candidate_state_with_parts",
)
