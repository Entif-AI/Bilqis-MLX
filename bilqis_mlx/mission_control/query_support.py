"""Pure CP03 selection, cursor, and page mechanics."""
from __future__ import annotations

import hashlib
import json
from types import MappingProxyType

from .contracts.trainer import (
    TrainerObservation, TrainerObservationV2, TrainerObservationV3,
    TrainerObservationV4, TrainerObservationV5, TrainerObservationV6, TrainerObservationV7,
)
from .contracts.codec import encode_record
from .contracts.dossier import CapabilityDossier
from .contracts.factory import FactoryCockpitSnapshot
from .contracts.envelopes import (
    PartialEnvelope, StaleEnvelope, UnavailableEnvelope, UnavailableReason,
)
from .contracts.events import (
    CandidateDecision, CorrectionEvent, FrameCompileReceipt, LearningEpisode,
    SalienceEvent,
)
from .contracts.model import CoverageState, WireRecord, is_wire_integer, require
from .contracts.registry import ALL_RECORD_TYPES
from .contracts.observability import (
    GenerationManifest, GenerationManifestV2, MemorySnapshot, NeuralRuntimeSample, ResourceSample,
    SemanticAtlasSnapshot, SemanticProjectionSnapshot, SemanticReleaseSnapshot,
    TeacherSnapshot,
)
from .contracts.notifications import Notification
from .query_contracts import (
    MAX_PAGE_ROWS_BYTES, QUERY_PAGE_SCHEMA, QueryFamily, QueryMode, QueryPage,
    QueryRequest, QueryState,
)
from .query_selection import matches_identity, record_sort_key, select_current
from .contracts.snapshots import (
    CapabilitySnapshot, CurriculumFrontier, OperatorView, RunContext,
    SchoolSnapshot,
)
from .semantic import (
    SemanticBankSnapshot, SemanticConceptSnapshot, SemanticGenerationState,
    SemanticHeldMappingSnapshot, SemanticSimilaritySnapshot,
)


FAMILY_TYPES = MappingProxyType({
    QueryFamily.RECORD: ALL_RECORD_TYPES,
    QueryFamily.RUN: (
        RunContext, OperatorView, TrainerObservation, TrainerObservationV2,
        TrainerObservationV3, TrainerObservationV4, TrainerObservationV5,
        TrainerObservationV6, TrainerObservationV7),
    QueryFamily.SCHOOL: (SchoolSnapshot, CurriculumFrontier),
    QueryFamily.CAPABILITY: (CapabilitySnapshot, CapabilityDossier),
    QueryFamily.EPISODE: (LearningEpisode, CandidateDecision),
    QueryFamily.GENERATION: (GenerationManifest, GenerationManifestV2),
    QueryFamily.SEMANTIC: (
        SemanticAtlasSnapshot, SemanticConceptSnapshot, SemanticGenerationState,
        SemanticBankSnapshot, SemanticHeldMappingSnapshot, SemanticSimilaritySnapshot,
        SemanticReleaseSnapshot, SemanticProjectionSnapshot,
    ),
    QueryFamily.FRAME: (FrameCompileReceipt,),
    QueryFamily.NEURAL: (NeuralRuntimeSample,),
    QueryFamily.MEMORY: (MemorySnapshot,),
    QueryFamily.TEACHER: (TeacherSnapshot,),
    QueryFamily.SALIENCE: (SalienceEvent,),
    QueryFamily.CORRECTION: (CorrectionEvent,),
    QueryFamily.RESOURCE: (ResourceSample,),
    QueryFamily.FACTORY: (FactoryCockpitSnapshot,),
    QueryFamily.NOTIFICATION: (Notification,),
})


def _rows_digest(rows) -> str:
    payload = [
        encode_record(item) if isinstance(item, WireRecord) else item.to_record()
        for item in rows
    ]
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cursor(request: QueryRequest, digest, offset: int) -> str:
    return f"cp03:{request.query_id}:{digest()}:{offset}"


def _offset(request: QueryRequest, rows, digest) -> int:
    if request.cursor is None:
        return 0
    prefix = f"cp03:{request.query_id}:"
    require(request.cursor.startswith(prefix), "QUERY_CURSOR_IDENTITY")
    parts = request.cursor[len(prefix):].split(":")
    require(
        len(parts) == 2 and len(parts[0]) == 64
        and all(char in "0123456789abcdef" for char in parts[0]),
        "QUERY_CURSOR_DIGEST",
    )
    require(parts[0] == digest(), "QUERY_CURSOR_STALE")
    require(parts[1].isdigit() and len(parts[1]) <= 16, "QUERY_CURSOR_OFFSET")
    offset = int(parts[1])
    require(is_wire_integer(offset) and offset >= 0, "QUERY_CURSOR_OFFSET")
    require(bool(rows) and offset < len(rows), "QUERY_CURSOR_RANGE")
    return offset


def _state(records, markers, *, historical_missing: bool) -> QueryState:
    if any(type(item) is StaleEnvelope for item in markers):
        return QueryState.STALE
    if any(type(item) is PartialEnvelope for item in markers):
        return QueryState.PARTIAL
    unavailable = next((item for item in markers if type(item) is UnavailableEnvelope), None)
    if unavailable is not None:
        if unavailable.reason is UnavailableReason.DENIED:
            return QueryState.DENIED
        if records:
            return QueryState.PARTIAL
        return {
            UnavailableReason.MISSING: QueryState.MISSING,
            UnavailableReason.DENIED: QueryState.DENIED,
            UnavailableReason.UNAVAILABLE: QueryState.UNAVAILABLE,
            UnavailableReason.UNKNOWN: QueryState.UNKNOWN,
        }[unavailable.reason]
    if any(item.meta.coverage is CoverageState.PARTIAL for item in records):
        return QueryState.PARTIAL
    if records:
        return QueryState.PRESENT
    return QueryState.MISSING if historical_missing else QueryState.EMPTY


def _encoded_size(row):
    encoded = encode_record(row) if isinstance(row, WireRecord) else row.to_record()
    return len(json.dumps(encoded, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _page_markers(markers, request, records, page_records, page_links):
    page_refs = {item.target_ref for item in page_links}
    relevant_ids = (
        {item.meta.record_id for item in page_records} | page_refs
        | {item.source_record_id for item in page_links})
    if request.reference is not None:
        relevant_ids.add(request.reference)
    return tuple(
        item for item in markers
        if ((type(item) is PartialEnvelope
             and item.partial_record_id in relevant_ids)
            or (type(item) is StaleEnvelope
                and (
                    item.stale_record_id in relevant_ids
                    or (request.family not in {QueryFamily.REFERENCE, QueryFamily.LINKS}
                        and not records)
                ))
            or (type(item) is UnavailableEnvelope
                and (not page_links
                     or item.resource in page_refs
                     or item.resource == request.reference)))
    )


def build_page(*, available: bool, request: QueryRequest, records, markers,
               links=(), exact_missing=False, rows_digest=None) -> QueryPage:
    rows = links if request.family in {QueryFamily.LINKS, QueryFamily.REFERENCE} else records
    digest_value = None

    def digest():
        nonlocal digest_value
        if digest_value is None:
            digest_value = rows_digest() if rows_digest is not None else _rows_digest(rows)
        return digest_value

    offset = _offset(request, rows, digest)
    page_rows, sizes = [], []
    rows_bytes = 2
    for row in rows[offset:offset + request.limit]:
        encoded_bytes = _encoded_size(row)
        require(encoded_bytes <= MAX_PAGE_ROWS_BYTES, "QUERY_ROW_TOO_LARGE")
        if page_rows and rows_bytes + encoded_bytes + 1 > MAX_PAGE_ROWS_BYTES:
            break
        rows_bytes += encoded_bytes + (1 if page_rows else 0)
        sizes.append(encoded_bytes)
        page_rows.append(row)
    marker_sizes = {}
    while True:
        page_records = tuple(page_rows) if rows is records else ()
        page_links = tuple(page_rows) if rows is links else ()
        page_markers = _page_markers(
            markers, request, records, page_records, page_links)
        marker_bytes = 2
        for marker in page_markers:
            key = marker.meta.record_id
            if key not in marker_sizes:
                marker_sizes[key] = _encoded_size(marker)
            marker_bytes += marker_sizes[key] + 1
        if rows_bytes + marker_bytes <= MAX_PAGE_ROWS_BYTES:
            break
        # Retain all relevant markers; shorten the page rather than rejecting
        # an otherwise valid query or silently dropping provenance.
        require(len(page_rows) > 1, "QUERY_ROW_TOO_LARGE")
        page_rows.pop()
        rows_bytes -= sizes.pop() + 1
    next_offset = offset + len(page_rows)
    next_cursor = _cursor(request, digest, next_offset) if next_offset < len(rows) else None
    state = (
        QueryState.UNAVAILABLE if not available
        else _state(
            page_records, page_markers,
            historical_missing=(exact_missing or request.mode is QueryMode.HISTORICAL),
        )
    )
    if page_links and not page_markers:
        state = QueryState.PRESENT
    coverage = (
        CoverageState.UNKNOWN if state in {
            QueryState.MISSING, QueryState.UNAVAILABLE, QueryState.DENIED, QueryState.UNKNOWN,
        }
        else CoverageState.PARTIAL if (
            state in {QueryState.PARTIAL, QueryState.STALE} or next_cursor is not None)
        else CoverageState.COMPLETE
    )
    return QueryPage(
        request=request, state=state, coverage=coverage,
        total_matches=len(rows), records=page_records,
        markers=page_markers, links=page_links, next_cursor=next_cursor,
    )


def encode_query_page(page: QueryPage) -> dict:
    return {
        "schema": QUERY_PAGE_SCHEMA,
        "query_id": page.request.query_id,
        "request": page.request.to_record(),
        "family": page.request.family.value,
        "mode": page.request.mode.value,
        "state": page.state.value,
        "coverage": page.coverage.value,
        "total_matches": page.total_matches,
        "returned": len(page.records) + len(page.links),
        "truncated": page.truncated,
        "next_cursor": page.next_cursor,
        "records": [encode_record(item) for item in page.records],
        "markers": [encode_record(item) for item in page.markers],
        "links": [item.to_record() for item in page.links],
    }
