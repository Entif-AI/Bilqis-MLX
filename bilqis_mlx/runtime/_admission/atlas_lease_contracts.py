"""Structural extraction from atlas_admission.py; behavior preserved."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import json
import re
from ..errors import ErrorBus, SCHOOL
from ..learning.champions import Checkpoint
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from ..semantics.domains import contract_digest
from .atlas_revalidation import SourceAuthorityRegistry

def _invalid(reason):
    ErrorBus.raise_(SCHOOL.BAMF_ATLAS_ADMISSION.INVALID, reason=reason)

def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None

def _name(value):
    return isinstance(value, str) and bool(value)

def _names(values, *, allow_empty=False):
    return (isinstance(values, tuple) and (allow_empty or bool(values)) and all(_name(value) for value in values)
            and values == tuple(sorted(set(values))))

@dataclass(frozen=True)
class LeaseRunIdentity:
    lineage_id: str
    initial_generation_digest: str
    topology_digest: str
    origin_checkpoint: Checkpoint
    verification_mode: str = field(default='DISPOSABLE_CONTRACT', init=False)
    schema_version: str = field(default='bilqis.c07.lease-run-identity/v1', init=False)

    def __post_init__(self):
        if (not _name(self.lineage_id) or not _sha(self.initial_generation_digest)
                or not _sha(self.topology_digest) or not isinstance(self.origin_checkpoint, Checkpoint)):
            _invalid('BAMF_ATLAS_LEASE_RUN_IDENTITY_INVALID')

@dataclass(frozen=True)
class DeltaBudgetPolicy:
    version: str = 'bilqis.c07.initial-delta/v1'
    max_capabilities: int = 9
    max_new_semantic_identities: int = 16

    def __post_init__(self):
        if (not _name(self.version) or type(self.max_capabilities) is not int
                or not 1 <= self.max_capabilities <= 9
                or type(self.max_new_semantic_identities) is not int
                or self.max_new_semantic_identities < 1
                or (self.version == 'bilqis.c07.initial-delta/v1'
                    and self.max_new_semantic_identities != 16)):
            _invalid('BAMF_ATLAS_DELTA_BUDGET_POLICY_INVALID')

@dataclass(frozen=True)
class AtlasSourceApproval:
    approval_id: str
    atlas_release_sha256: str
    source_family_ids: tuple[str, ...]
    operator_ids: tuple[str, ...]
    rights_receipt_sha256: str
    rights_epoch: int
    prerequisite_policy_sha256: str
    progression_policy_sha256: str
    authority_audit_receipt_sha256: str
    audit_passed: bool
    rights_compatible: bool
    source_owner: str
    signature_hex: str
    delta_budget_policy: DeltaBudgetPolicy = field(default_factory=DeltaBudgetPolicy)
    verification_mode: str = field(default='DISPOSABLE_CONTRACT', init=False)
    schema_version: str = field(default='bilqis.c07.atlas-source-approval/v1', init=False)

    def __post_init__(self):
        if (not _name(self.approval_id) or not _name(self.source_owner)
                or not _names(self.source_family_ids) or not _names(self.operator_ids, allow_empty=True)
                or not isinstance(self.delta_budget_policy, DeltaBudgetPolicy)
                or not all(_sha(value) for value in (self.atlas_release_sha256, self.rights_receipt_sha256,
                    self.prerequisite_policy_sha256, self.progression_policy_sha256,
                    self.authority_audit_receipt_sha256))
                or type(self.rights_epoch) is not int or self.rights_epoch < 0
                or type(self.audit_passed) is not bool or type(self.rights_compatible) is not bool
                or not isinstance(self.signature_hex, str)
                or re.fullmatch('[0-9a-f]{128}', self.signature_hex) is None):
            _invalid('BAMF_ATLAS_SOURCE_APPROVAL_INVALID')

    def signing_bytes(self):
        payload = asdict(self)
        del payload['signature_hex']
        return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode('utf-8')

    def verify_signature(self, registry):
        if not isinstance(registry, SourceAuthorityRegistry):
            _invalid('BAMF_ATLAS_SOURCE_REGISTRY_REQUIRED')
        registry.verify_detached(self.source_owner,
            DependencyRef(DependencyKind.ARTIFACT, 'atlas-approval:' + self.approval_id),
            self.signature_hex, self.signing_bytes())

    def verify(self, registry):
        self.verify_signature(registry)
        if not self.audit_passed or not self.rights_compatible:
            _invalid('BAMF_ATLAS_SOURCE_OR_RIGHTS_HELD')

@dataclass(frozen=True)
class ResourceCeiling:
    max_semantic_banks: int
    max_motif_pages: int
    max_total_semantic_identities: int
    max_memory_bytes: int
    max_disk_bytes: int

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            _invalid('BAMF_ATLAS_RESOURCE_CEILING_INVALID')

@dataclass(frozen=True)
class AtlasAdmissionLease:
    lease_id: str
    run_identity: LeaseRunIdentity
    source_approval: AtlasSourceApproval
    resource_ceiling: ResourceCeiling
    requested_at: int
    human_command_sha256: str
    admission_policy: str = field(default='atlas-release', init=False)
    schema_version: str = field(default='bilqis.c07.atlas-admission-lease/v1', init=False)

    def __post_init__(self):
        if (not _name(self.lease_id) or not isinstance(self.run_identity, LeaseRunIdentity)
                or not isinstance(self.source_approval, AtlasSourceApproval)
                or not isinstance(self.resource_ceiling, ResourceCeiling)
                or type(self.requested_at) is not int or self.requested_at < 0
                or not _sha(self.human_command_sha256)):
            _invalid('BAMF_ATLAS_ADMISSION_LEASE_INVALID')

    def digest(self):
        return contract_digest(self)
