"""A10.1 provenance-safe BRAVO evidence records and public-fixture boundary.

This is an application adapter contract, not a Rosetta Core type.  It preserves
source identity, source spans, interpretation revision, rights and explicit
semantic references without minting source labels as semantic authority.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import (
    TypedValue, UnitConversion, default_registry, operator_grant_digest,
)
from bilqis_mlx.semantics.released_frame_schemas import (
    lookup_source_pinned_frame_schema,
)


from bilqis_mlx.source_adapters.evidence.source_manifests import (
    PRIVATE_REAL_FIXTURE_MANIFEST_CID,
    PRIVATE_REAL_FIXTURE_SOURCE,
    PUBLIC_DUPLICATE_MANIFEST_CID,
    PUBLIC_DUPLICATE_SOURCE,
    PUBLIC_FIXTURE_MANIFEST_CID,
    PUBLIC_FIXTURE_REPACK_MANIFEST_CID,
    PUBLIC_FIXTURE_SOURCE,
    PUBLIC_INDEPENDENT_BUNDLE_SOURCE,
    PUBLIC_INDEPENDENT_MANIFEST_CID,
    PUBLIC_INDEPENDENT_SOURCE,
    LEGACY_PUBLIC_FIXTURE_MANIFEST_CID,
    _PRIVATE_REAL_MANIFEST,
    _PRIVATE_REAL_SOURCE_DIGEST,
    _PUBLIC_MANIFEST,
    source_family_id,
    source_manifest_semantic_authority,
)
from bilqis_mlx.source_adapters.evidence.evidence_types import (
    SCHEMA, PRIVATE_REAL, PUBLIC_FIXTURE, UNCLASSIFIED,
    BamfEvidenceSnapshot, EvidenceDerivation, EvidenceFrame, EvidenceRecord,
    EvidenceRights, EvidenceSemanticAuthority, EventTime, ReportedValue,
    SourceSpan, _fail,
)


_DURATION_FIELD_PARTS = 2
_STUDY_SOURCE_ROW_KEY = "LEXSENSE-24e0d37974513f"
_EVIDENCE_SCHEMA_ID = "frame:bravo.evidence.actor/v1"
_EVIDENCE_SCHEMA_REVISION = 1
_AGENT_ROLE_ID = "agent"
_HOUR_UNIT = "h"
_MINUTE_UNIT = "min"


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


def build_private_real_fixture_snapshot(
    *, atlas_selection: AtlasArtifactSelection,
) -> tuple[BamfEvidenceSnapshot, EvidenceRights]:
    """Create a synthetic protected source that exercises the PRIVATE_REAL lifecycle."""
    authority = resolve_public_fixture_authority(atlas_selection)
    if authority != _PRIVATE_REAL_MANIFEST.semantic_authority:
        _fail("BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH")
    rights = EvidenceRights(PRIVATE_REAL, "TRAINING", True, False)
    record = parse_public_fixture_source(
        PRIVATE_REAL_FIXTURE_SOURCE,
        category_ref=authority.category_ref,
        hour_unit_ref=authority.hour_unit_ref,
        agent_role_ref=authority.agent_role_ref,
    )
    snapshot = BamfEvidenceSnapshot(
        snapshot_id="bamf-private-real-fixture-001",
        source_manifest_cid=PRIVATE_REAL_FIXTURE_MANIFEST_CID,
        source_byte_digest=_PRIVATE_REAL_SOURCE_DIGEST,
        interpretation_revision="bravo-private-real-fixture/v1",
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
