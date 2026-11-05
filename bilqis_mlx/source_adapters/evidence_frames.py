"""A10.1 provenance-safe BRAVO evidence records and public-fixture boundary.

This is an application adapter contract, not a Rosetta Core type.  It preserves
source identity, source spans, interpretation revision, rights and explicit
semantic references without minting source labels as semantic authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import (
    TypedValue, UnitConversion, default_registry, operator_grant_digest,
)
from bilqis_mlx.semantics.released_frame_schemas import (
    lookup_source_pinned_frame_schema,
)


from bilqis_mlx.source_adapters.evidence_types import (
    SCHEMA, PRIVATE_REAL, PUBLIC_FIXTURE, UNCLASSIFIED,
    BamfEvidenceSnapshot, EvidenceDerivation, EvidenceFrame, EvidenceRecord,
    EvidenceRights, EvidenceSemanticAuthority, EventTime, ReportedValue,
    SourceSpan, _SHA, _fail, _text,
)


PUBLIC_FIXTURE_SOURCE = "actor=actor_01; category=study; status=completed; duration=0.25 h"
_DURATION_FIELD_PARTS = 2
_STUDY_SOURCE_ROW_KEY = "LEXSENSE-24e0d37974513f"
_EVIDENCE_SCHEMA_ID = "frame:bravo.evidence.actor/v1"
_EVIDENCE_SCHEMA_REVISION = 1
_AGENT_ROLE_ID = "agent"
_HOUR_UNIT = "h"
_MINUTE_UNIT = "min"
_PINNED_EVIDENCE_RELEASE = (
    "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306")
_PINNED_STUDY_CATEGORY = (
    "https://github.com/Entif-AI/Bilqis-MLX/id/sense/"
    "NI-LEXICON-CURRICULUM/LEXROOT-3e51e33b4a970f/STEM%203/BSC")


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


def resolve_public_fixture_authority(
    atlas_selection: AtlasArtifactSelection,
) -> EvidenceSemanticAuthority:
    """Re-enter the accepted A01/A03/operator owners for fixture semantics."""
    if type(atlas_selection) is not AtlasArtifactSelection:
        _fail("BAMF_EVIDENCE_ATLAS_SELECTION_REQUIRED")
    snapshot = load_pinned_atlas_snapshot(atlas_selection)
    category_matches = tuple(
        item.concept.semantic_id
        for item in snapshot.concepts
        if any(source.key == _STUDY_SOURCE_ROW_KEY
               for source in item.concept.source_rows)
    )
    if len(category_matches) != 1:
        _fail("BAMF_EVIDENCE_CATEGORY_AUTHORITY_MISMATCH")
    schema, _ = lookup_source_pinned_frame_schema(
        _EVIDENCE_SCHEMA_ID, _EVIDENCE_SCHEMA_REVISION,
        source_family="evidence", atlas_selection=atlas_selection)
    roles = tuple(role for role in schema.roles if role.role_id == _AGENT_ROLE_ID)
    if (len(roles) != 1 or roles[0].min_cardinality != 1
            or roles[0].max_cardinality != 1
            or "Entity" not in roles[0].allowed_type_ids):
        _fail("BAMF_EVIDENCE_AGENT_ROLE_AUTHORITY_MISMATCH")
    # These constructors re-enter the current cognitive-operator declarations;
    # neither the fixture nor the caller gets to mint a unit or conversion edge.
    TypedValue("UnitName", _HOUR_UNIT, snapshot.release_sha256)
    UnitConversion(_HOUR_UNIT, _MINUTE_UNIT, 60, 1)
    operator = default_registry(snapshot.release_sha256).resolve("UNIT_CONVERT")
    return EvidenceSemanticAuthority(
        snapshot.release_sha256, category_matches[0], _HOUR_UNIT,
        roles[0].role_id, operator.operator_id, operator_grant_digest(operator))


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
    (_SourceFamilyBinding(_PUBLIC_SOURCE_SPAN, _PUBLIC_FAMILY_ID),))
LEGACY_PUBLIC_FIXTURE_MANIFEST_CID = (
    "public-fixture:bravo-a10-1/v1:" + _PUBLIC_SOURCE_DIGEST)
PUBLIC_FIXTURE_MANIFEST_CID = _family_manifest_cid("bravo-a10-1", _PUBLIC_MANIFEST)
PUBLIC_FIXTURE_REPACK_MANIFEST_CID = _family_manifest_cid(
    "bravo-a10-1-repack", _PUBLIC_MANIFEST)

PUBLIC_DUPLICATE_SOURCE = PUBLIC_FIXTURE_SOURCE + "\n" + PUBLIC_FIXTURE_SOURCE
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

PUBLIC_INDEPENDENT_SOURCE = (
    "actor=actor_02; category=study; status=completed; duration=0.50 h")
PUBLIC_INDEPENDENT_BUNDLE_SOURCE = (
    PUBLIC_FIXTURE_SOURCE + "\n" + PUBLIC_INDEPENDENT_SOURCE)
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
    # Exact accepted pre-manifest fixture identity. This is a single
    # compatibility alias, not a generic legacy parser.
    (LEGACY_PUBLIC_FIXTURE_MANIFEST_CID, _PUBLIC_MANIFEST),
    (PUBLIC_FIXTURE_MANIFEST_CID, _PUBLIC_MANIFEST),
    (PUBLIC_FIXTURE_REPACK_MANIFEST_CID, _PUBLIC_MANIFEST),
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


def verification_state(record: EvidenceRecord) -> str:
    if "EXPECTED_REPORT_MISSING" in record.alternatives:
        return "VERIFICATION_NEEDED"
    if record.alternatives:
        return "ALTERNATIVES_PRESENT"
    return "ADJUDICATED"


def parse_public_fixture_source(
    source_text: str, *, category_ref: str, hour_unit_ref: str, agent_role_ref: str,
) -> EvidenceRecord:
    """Parse the one rights-cleared literal fixture without using free-form inference."""
    expected_parts = (
        ("actor", None), ("category", None), ("status", "completed"),
        ("duration", None),
    )
    try:
        fields = {}
        for part in source_text.split("; "):
            key, value = part.split("=", 1)
            fields[key] = value
        if tuple(fields) != tuple(key for key, _ in expected_parts):
            raise ValueError
        if fields["status"] != "completed":
            raise ValueError
        duration_parts = fields["duration"].split(" ")
        if len(duration_parts) != _DURATION_FIELD_PARTS or duration_parts[1] != "h":
            raise ValueError
        Decimal(duration_parts[0])
    except (ValueError, InvalidOperation):
        _fail("BAMF_EVIDENCE_PUBLIC_FIXTURE_PARSE_INVALID")
    return EvidenceRecord(
        record_id="fixture-001", actor_ref=fields["actor"],
        source_span=SourceSpan(0, len(source_text)), category_ref=category_ref,
        category_label=fields["category"], status="COMPLETED",
        reported_value=ReportedValue(duration_parts[0], hour_unit_ref),
        unit_label=duration_parts[1], event_time=EventTime(None, None, "UTC"),
        observed_at="2026-01-01T00:00:00Z", alternatives=(),
        adjudication_ref="adjudication:fixture-001", agent_role_ref=agent_role_ref,
    )


def build_public_fixture_snapshot(
    *, atlas_selection: AtlasArtifactSelection,
) -> tuple[BamfEvidenceSnapshot, EvidenceRights]:
    """Create the literal public fixture prescribed by A10 without private data."""
    authority = resolve_public_fixture_authority(atlas_selection)
    if authority != _PUBLIC_MANIFEST.semantic_authority:
        _fail("BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH")
    rights = EvidenceRights(PUBLIC_FIXTURE, "TRAINING", True, True)
    record = parse_public_fixture_source(
        PUBLIC_FIXTURE_SOURCE, category_ref=authority.category_ref,
        hour_unit_ref=authority.hour_unit_ref,
        agent_role_ref=authority.agent_role_ref)
    digest = sha256(PUBLIC_FIXTURE_SOURCE.encode("utf-8")).hexdigest()
    snapshot = BamfEvidenceSnapshot(
        snapshot_id="bamf-public-fixture-001",
        source_manifest_cid=PUBLIC_FIXTURE_MANIFEST_CID,
        source_byte_digest=digest,
        interpretation_revision="bravo-public-fixture/v1",
        semantic_release=authority.semantic_release,
        rights=rights,
        records=(record,),
    )
    return snapshot, rights


def public_export(candidate_set):
    """Fail closed unless the compiled set is wholly public-export qualified."""
    holds = getattr(candidate_set, "holds", ())
    if any(getattr(item, "reason", "") == "RIGHTS_NOT_PUBLIC_TRAINING_QUALIFIED"
           for item in holds):
        _fail("BAMF_EVIDENCE_PUBLIC_EXPORT_HELD")
    rights = getattr(candidate_set, "rights", None)
    if (type(rights) is not EvidenceRights or rights.regime != PUBLIC_FIXTURE
            or not rights.public_export_allowed):
        _fail("BAMF_EVIDENCE_PUBLIC_EXPORT_FORBIDDEN")
    return candidate_set
