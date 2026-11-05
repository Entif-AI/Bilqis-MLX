"""Pinned BRAVO evidence source manifests and family-resolution ownership."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from bilqis_mlx.semantics.cognitive_operators import default_registry, operator_grant_digest
from bilqis_mlx.source_adapters.evidence_types import (
    BamfEvidenceSnapshot,
    EvidenceRecord,
    EvidenceSemanticAuthority,
    SourceSpan,
    _SHA,
    _fail,
    _text,
)


PUBLIC_FIXTURE_SOURCE = "actor=actor_01; category=study; status=completed; duration=0.25 h"
PRIVATE_REAL_FIXTURE_SOURCE = (
    "actor=PROTECTED_SENTINEL_DO_NOT_EXPORT; category=study; "
    "status=completed; duration=0.25 h"
)
PUBLIC_DUPLICATE_SOURCE = PUBLIC_FIXTURE_SOURCE + "\n" + PUBLIC_FIXTURE_SOURCE
PUBLIC_INDEPENDENT_SOURCE = (
    "actor=actor_02; category=study; status=completed; duration=0.50 h")
PUBLIC_INDEPENDENT_BUNDLE_SOURCE = (
    PUBLIC_FIXTURE_SOURCE + "\n" + PUBLIC_INDEPENDENT_SOURCE)

_PINNED_EVIDENCE_RELEASE = (
    "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306")
_PINNED_STUDY_CATEGORY = (
    "https://github.com/Entif-AI/Bilqis-MLX/id/sense/"
    "NI-LEXICON-CURRICULUM/LEXROOT-3e51e33b4a970f/STEM%203/BSC")
_HOUR_UNIT = "h"
_AGENT_ROLE_ID = "agent"


def _digest(*parts: str) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _SourceFamilyBinding:
    source_span: SourceSpan
    family_id: str

    def __post_init__(self) -> None:
        if type(self.source_span) is not SourceSpan or not _text(self.family_id):
            _fail("BAMF_EVIDENCE_FAMILY_INPUT_INVALID")


@dataclass(frozen=True)
class _SourceFamilyManifest:
    source_byte_digest: str
    semantic_authority: EvidenceSemanticAuthority
    bindings: tuple[_SourceFamilyBinding, ...]

    def __post_init__(self) -> None:
        if (not _SHA.fullmatch(self.source_byte_digest)
                or type(self.semantic_authority) is not EvidenceSemanticAuthority
                or type(self.bindings) is not tuple or not self.bindings
                or any(type(item) is not _SourceFamilyBinding for item in self.bindings)
                or len({(item.source_span.start, item.source_span.end)
                        for item in self.bindings}) != len(self.bindings)):
            _fail("BAMF_EVIDENCE_FAMILY_INPUT_INVALID")


def _family_manifest_cid(name: str, manifest: _SourceFamilyManifest) -> str:
    authority = manifest.semantic_authority
    body = [
        manifest.source_byte_digest,
        authority.semantic_release,
        authority.category_ref,
        authority.hour_unit_ref,
        authority.agent_role_ref,
        authority.unit_operator_id,
        authority.unit_operator_grant_sha256,
        *[f"{item.source_span.start}:{item.source_span.end}:{item.family_id}"
          for item in manifest.bindings],
    ]
    return f"public-fixture:{name}/v1:" + _digest(*body)


_PUBLIC_FAMILY_ID = "evidence-family:" + _digest(
    "bravo.public-fixture", "episode-001")
_PUBLIC_INDEPENDENT_FAMILY_ID = "evidence-family:" + _digest(
    "bravo.public-fixture", "episode-002")
_PUBLIC_SEMANTIC_AUTHORITY = EvidenceSemanticAuthority(
    _PINNED_EVIDENCE_RELEASE,
    _PINNED_STUDY_CATEGORY,
    _HOUR_UNIT,
    _AGENT_ROLE_ID,
    "UNIT_CONVERT",
    "059ccd2a33330473973914b94fc0d772d6f845b6ee9c8e736f1876e6a9823e9f",
)
_PUBLIC_SOURCE_DIGEST = sha256(PUBLIC_FIXTURE_SOURCE.encode("utf-8")).hexdigest()
_PUBLIC_SOURCE_SPAN = SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE))
_PUBLIC_MANIFEST = _SourceFamilyManifest(
    _PUBLIC_SOURCE_DIGEST,
    _PUBLIC_SEMANTIC_AUTHORITY,
    (_SourceFamilyBinding(_PUBLIC_SOURCE_SPAN, _PUBLIC_FAMILY_ID),),
)
LEGACY_PUBLIC_FIXTURE_MANIFEST_CID = (
    "public-fixture:bravo-a10-1/v1:" + _PUBLIC_SOURCE_DIGEST)
PUBLIC_FIXTURE_MANIFEST_CID = _family_manifest_cid("bravo-a10-1", _PUBLIC_MANIFEST)
PUBLIC_FIXTURE_REPACK_MANIFEST_CID = _family_manifest_cid(
    "bravo-a10-1-repack", _PUBLIC_MANIFEST)

_PRIVATE_REAL_FAMILY_ID = "evidence-family:" + _digest(
    "bravo.private-real-fixture", "episode-001")
_PRIVATE_REAL_SOURCE_DIGEST = sha256(
    PRIVATE_REAL_FIXTURE_SOURCE.encode("utf-8")).hexdigest()
_PRIVATE_REAL_SOURCE_SPAN = SourceSpan(0, len(PRIVATE_REAL_FIXTURE_SOURCE))
_PRIVATE_REAL_MANIFEST = _SourceFamilyManifest(
    _PRIVATE_REAL_SOURCE_DIGEST,
    _PUBLIC_SEMANTIC_AUTHORITY,
    (_SourceFamilyBinding(_PRIVATE_REAL_SOURCE_SPAN, _PRIVATE_REAL_FAMILY_ID),),
)
PRIVATE_REAL_FIXTURE_MANIFEST_CID = (
    "private-real:bravo-a10-private/v1:"
    + _digest(
        _PRIVATE_REAL_MANIFEST.source_byte_digest,
        _PRIVATE_REAL_MANIFEST.semantic_authority.semantic_release,
        _PRIVATE_REAL_MANIFEST.semantic_authority.category_ref,
        _PRIVATE_REAL_MANIFEST.semantic_authority.hour_unit_ref,
        _PRIVATE_REAL_MANIFEST.semantic_authority.agent_role_ref,
        _PRIVATE_REAL_MANIFEST.semantic_authority.unit_operator_id,
        _PRIVATE_REAL_MANIFEST.semantic_authority.unit_operator_grant_sha256,
        f"0:{len(PRIVATE_REAL_FIXTURE_SOURCE)}:{_PRIVATE_REAL_FAMILY_ID}",
    )
)

_DUPLICATE_DIGEST = sha256(PUBLIC_DUPLICATE_SOURCE.encode("utf-8")).hexdigest()
_DUPLICATE_SECOND_START = len(PUBLIC_FIXTURE_SOURCE) + 1
_DUPLICATE_MANIFEST = _SourceFamilyManifest(
    _DUPLICATE_DIGEST,
    _PUBLIC_SEMANTIC_AUTHORITY,
    (
        _SourceFamilyBinding(SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE)), _PUBLIC_FAMILY_ID),
        _SourceFamilyBinding(
            SourceSpan(_DUPLICATE_SECOND_START,
                       _DUPLICATE_SECOND_START + len(PUBLIC_FIXTURE_SOURCE)),
            _PUBLIC_FAMILY_ID),
    ),
)
PUBLIC_DUPLICATE_MANIFEST_CID = _family_manifest_cid(
    "bravo-a10-duplicate", _DUPLICATE_MANIFEST)

_INDEPENDENT_DIGEST = sha256(PUBLIC_INDEPENDENT_BUNDLE_SOURCE.encode("utf-8")).hexdigest()
_INDEPENDENT_SECOND_START = len(PUBLIC_FIXTURE_SOURCE) + 1
_INDEPENDENT_MANIFEST = _SourceFamilyManifest(
    _INDEPENDENT_DIGEST,
    _PUBLIC_SEMANTIC_AUTHORITY,
    (
        _SourceFamilyBinding(SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE)), _PUBLIC_FAMILY_ID),
        _SourceFamilyBinding(
            SourceSpan(_INDEPENDENT_SECOND_START,
                       _INDEPENDENT_SECOND_START + len(PUBLIC_INDEPENDENT_SOURCE)),
            _PUBLIC_INDEPENDENT_FAMILY_ID),
    ),
)
PUBLIC_INDEPENDENT_MANIFEST_CID = _family_manifest_cid(
    "bravo-a10-independent", _INDEPENDENT_MANIFEST)

_SOURCE_FAMILY_MANIFESTS = (
    (LEGACY_PUBLIC_FIXTURE_MANIFEST_CID, _PUBLIC_MANIFEST),
    (PUBLIC_FIXTURE_MANIFEST_CID, _PUBLIC_MANIFEST),
    (PUBLIC_FIXTURE_REPACK_MANIFEST_CID, _PUBLIC_MANIFEST),
    (PRIVATE_REAL_FIXTURE_MANIFEST_CID, _PRIVATE_REAL_MANIFEST),
    (PUBLIC_DUPLICATE_MANIFEST_CID, _DUPLICATE_MANIFEST),
    (PUBLIC_INDEPENDENT_MANIFEST_CID, _INDEPENDENT_MANIFEST),
)


def source_family_id(snapshot: BamfEvidenceSnapshot, record: EvidenceRecord) -> str:
    """Resolve episode-family identity from the source owner's pinned manifest."""
    if type(snapshot) is not BamfEvidenceSnapshot or type(record) is not EvidenceRecord:
        _fail("BAMF_EVIDENCE_FAMILY_INPUT_INVALID")
    matches = tuple(
        manifest for cid, manifest in _SOURCE_FAMILY_MANIFESTS
        if cid == snapshot.source_manifest_cid)
    if len(matches) != 1 or matches[0].source_byte_digest != snapshot.source_byte_digest:
        _fail("BAMF_EVIDENCE_FAMILY_INPUT_INVALID")
    manifest = matches[0]
    matches = tuple(
        item for item in manifest.bindings if item.source_span == record.source_span)
    if len(matches) != 1:
        _fail("BAMF_EVIDENCE_FAMILY_INPUT_INVALID")
    return matches[0].family_id


def source_manifest_semantic_authority(
    snapshot: BamfEvidenceSnapshot,
) -> EvidenceSemanticAuthority:
    """Resolve the source owner's registered semantic binding for a snapshot."""
    if type(snapshot) is not BamfEvidenceSnapshot:
        _fail("BAMF_EVIDENCE_FAMILY_INPUT_INVALID")
    matches = tuple(
        manifest for cid, manifest in _SOURCE_FAMILY_MANIFESTS
        if cid == snapshot.source_manifest_cid)
    if (len(matches) != 1
            or matches[0].source_byte_digest != snapshot.source_byte_digest
            or matches[0].semantic_authority.semantic_release
            != snapshot.semantic_release):
        _fail("BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH")
    authority = matches[0].semantic_authority
    operator = default_registry(authority.semantic_release).resolve(
        authority.unit_operator_id)
    if operator_grant_digest(operator) != authority.unit_operator_grant_sha256:
        _fail("BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH")
    return authority
