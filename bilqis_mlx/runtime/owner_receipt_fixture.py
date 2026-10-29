"""C-owned opaque receiving fixtures, not production A/B receipt interfaces."""
from dataclasses import asdict, dataclass
import hashlib
import json

from .akasha_outbox import AkashaEvent, AkashaEventKind, OWNER_FIXTURE_KINDS, _invalid, _sha, _name
from .atlas_revalidation import SourceAuthorityRegistry
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


@dataclass(frozen=True)
class OwnerReceiptFixture:
    category: AkashaEventKind
    source_event_id: str
    producer_id: str
    artifact_schema: str
    artifact_sha256: str
    source_owner: str
    source_time: int
    effective_time: int
    observed_at: int
    recorded_at: int
    signature_hex: str
    verification_mode: str = 'DISPOSABLE_CONTRACT'
    schema_version: str = 'bilqis.c10.owner-receipt-fixture/v1'

    def __post_init__(self):
        if (not isinstance(self.category, AkashaEventKind) or self.category not in OWNER_FIXTURE_KINDS
                or any(not _name(value) for value in (self.source_event_id, self.producer_id, self.artifact_schema, self.source_owner))
                or not _sha(self.artifact_sha256)
                or any(type(value) is not int or value < 0 for value in
                       (self.source_time, self.effective_time, self.observed_at, self.recorded_at))
                or self.source_time > self.observed_at or self.observed_at > self.recorded_at
                or self.verification_mode != 'DISPOSABLE_CONTRACT'
                or self.schema_version != 'bilqis.c10.owner-receipt-fixture/v1'):
            _invalid('BAMF_C10_OWNER_RECEIPT_FIXTURE_INVALID')

    def signing_bytes(self):
        return _canonical({key: value for key, value in asdict(self).items() if key != 'signature_hex'})

    def digest(self):
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()

    def dependency(self):
        identity = hashlib.sha256(_canonical([self.producer_id, self.source_event_id])).hexdigest()
        return DependencyRef(DependencyKind.ARTIFACT, 'projection-fixture:' + self.category.value + ':' + identity)


def project_owner_receipt_fixture(receipt, artifact_bytes, registry):
    """Verify artifact attestation only; confer no domain, rights or learning authority."""
    if (not isinstance(receipt, OwnerReceiptFixture) or not isinstance(artifact_bytes, bytes)
            or not isinstance(registry, SourceAuthorityRegistry)
            or hashlib.sha256(artifact_bytes).hexdigest() != receipt.artifact_sha256):
        _invalid('BAMF_C10_OWNER_ARTIFACT_DRIFT')
    registry.verify_detached(receipt.source_owner, receipt.dependency(),
                             receipt.signature_hex, receipt.signing_bytes())
    return AkashaEvent.from_payload(kind=receipt.category, subject_id=receipt.dependency().key,
        source_receipt_sha256=receipt.digest(), payload={
            'owner_source_event_id': receipt.source_event_id, 'producer_id': receipt.producer_id,
            'artifact_schema': receipt.artifact_schema, 'artifact_sha256': receipt.artifact_sha256,
            'verification_mode': receipt.verification_mode},
        source_time=receipt.source_time, effective_time=receipt.effective_time,
        observed_at=receipt.observed_at, recorded_at=receipt.recorded_at)
