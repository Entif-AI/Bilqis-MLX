"""A12 exact export-clearance contract."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import re

from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry

from ..atlas.snapshot_contracts import AtlasArtifactSelection, _require_registered_source_pin
from ..atlas_projection import HEX64, _canonical_bytes, _fail
from ..cognitive_dependencies import DependencyKind, DependencyRef
from ..context_eligibility import SourceFrontier
from ..domains import contract_digest
from .contracts import _digests

_SIGNATURE = re.compile(r"[0-9a-f]{128}")
EXPORT_CLEARANCE_SCHEMA = "bilqis.a12.export-clearance/v1"


@dataclass(frozen=True)
class ExportClearanceReceipt:
    """Source-owner statement for one exact export set at one rights frontier."""

    source_owner: str
    atlas_bundle_id: str
    semantic_release: str
    source_bundle_id: str
    source_frontier_sha256: str
    rights_epoch: int
    correction_generation: int
    export_artifact_digests: tuple[str, ...]
    private_artifact_digests: tuple[str, ...]
    revoked_artifact_digests: tuple[str, ...]
    revocation_lineage: tuple[str, ...]
    signature_hex: str
    schema_version: str = EXPORT_CLEARANCE_SCHEMA

    def __post_init__(self):
        exported = set(self.export_artifact_digests)
        private = set(self.private_artifact_digests)
        revoked = set(self.revoked_artifact_digests)
        if (type(self.source_owner) is not str or not self.source_owner
                or any(type(value) is not str or not HEX64.fullmatch(value)
                       for value in (self.atlas_bundle_id, self.semantic_release,
                                     self.source_bundle_id, self.source_frontier_sha256))
                or type(self.rights_epoch) is not int or self.rights_epoch < 0
                or type(self.correction_generation) is not int or self.correction_generation < 0
                or not _digests(self.export_artifact_digests)
                or not _digests(self.private_artifact_digests, allow_empty=True)
                or not _digests(self.revoked_artifact_digests, allow_empty=True)
                or not _digests(self.revocation_lineage, allow_empty=True)
                or exported & (private | revoked) or private & revoked
                or type(self.signature_hex) is not str
                or _SIGNATURE.fullmatch(self.signature_hex) is None
                or self.schema_version != EXPORT_CLEARANCE_SCHEMA):
            _fail("A12_EXPORT_CLEARANCE_INVALID")

    def signing_bytes(self):
        payload = asdict(self)
        del payload["signature_hex"]
        return _canonical_bytes(payload)

    def dependency(self):
        return DependencyRef(
            DependencyKind.ARTIFACT,
            "a12-export:" + self.source_bundle_id + ":" + self.semantic_release)

    @property
    def clearance_sha256(self):
        return sha256(self.signing_bytes()).hexdigest()


def validate_export_clearance_context(
        receipt, selection, source_frontier, artifact_digests, authority_registry):
    """Bind a verified owner receipt to the selected release and live rights state."""
    if (type(receipt) is not ExportClearanceReceipt
            or type(selection) is not AtlasArtifactSelection
            or type(source_frontier) is not SourceFrontier
            or not _digests(artifact_digests)
            or not isinstance(authority_registry, SourceAuthorityRegistry)):
        _fail("A12_EXPORT_CLEARANCE_CONTEXT_INVALID")
    receipt.__post_init__()
    source_frontier.__post_init__()
    authority_registry.verify_detached(
        receipt.source_owner, receipt.dependency(),
        receipt.signature_hex, receipt.signing_bytes())
    _require_registered_source_pin(selection)
    if (receipt.atlas_bundle_id != selection.bundle_id
            or receipt.semantic_release != selection.release_sha256
            or receipt.source_bundle_id != selection.source_bundle_id):
        _fail("A12_EXPORT_CLEARANCE_RELEASE_DRIFT")
    if (receipt.rights_epoch != source_frontier.rights_epoch
            or receipt.correction_generation != source_frontier.correction_generation
            or receipt.source_frontier_sha256 != contract_digest(source_frontier)):
        _fail("A12_EXPORT_CLEARANCE_FRONTIER_DRIFT")
    if any(grant.rights_epoch != source_frontier.rights_epoch
           or grant.correction_generation != source_frontier.correction_generation
           or grant.semantic_release != receipt.semantic_release
           for grant in source_frontier.grants):
        _fail("A12_EXPORT_CLEARANCE_GRANT_DRIFT")
    if artifact_digests != receipt.export_artifact_digests:
        _fail("A12_EXPORT_CLEARANCE_ARTIFACT_DRIFT")
    return receipt.clearance_sha256
