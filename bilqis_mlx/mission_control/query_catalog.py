"""Ephemeral CP03 bounded query catalog over authoritative CP02 records."""
from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType

from .codec import encode_record
from .envelopes import (
    PartialEnvelope, StaleEnvelope, UnavailableEnvelope, UnavailableReason,
)
from .events import (
    CandidateDecision, CorrectionEvent, FrameCompileReceipt, LearningEpisode,
    SalienceEvent,
)
from .model import CoverageState, WireRecord, is_wire_integer, require
from .observability import (
    GenerationManifest, MemorySnapshot, NeuralRuntimeSample, ResourceSample,
    SemanticAtlasSnapshot, TeacherSnapshot,
)
from .query_contracts import (
    QUERY_PAGE_SCHEMA, QueryFamily, QueryLink, QueryMode, QueryPage, QueryRequest,
    QueryState,
)
from .snapshots import (
    CapabilitySnapshot, CurriculumFrontier, OperatorView, RunContext,
    SchoolSnapshot,
)


_FAMILY_TYPES = MappingProxyType({
    QueryFamily.RUN: (RunContext, OperatorView),
    QueryFamily.SCHOOL: (SchoolSnapshot, CurriculumFrontier),
    QueryFamily.CAPABILITY: (CapabilitySnapshot,),
    QueryFamily.EPISODE: (LearningEpisode, CandidateDecision),
    QueryFamily.GENERATION: (GenerationManifest,),
    QueryFamily.SEMANTIC: (SemanticAtlasSnapshot,),
    QueryFamily.FRAME: (FrameCompileReceipt,),
    QueryFamily.NEURAL: (NeuralRuntimeSample,),
    QueryFamily.MEMORY: (MemorySnapshot,),
    QueryFamily.TEACHER: (TeacherSnapshot,),
    QueryFamily.SALIENCE: (SalienceEvent,),
    QueryFamily.CORRECTION: (CorrectionEvent,),
    QueryFamily.RESOURCE: (ResourceSample,),
})


def _record_sort_key(record: WireRecord):
    run = record.meta.run
    return (
        "" if run is None else run.run_id,
        -1 if run is None else run.generation,
        -1 if record.meta.as_of is None else record.meta.as_of,
        record.schema_version,
        record.meta.record_id,
    )


def _cursor(request: QueryRequest, offset: int) -> str:
    return f"cp03:{request.query_id}:{offset}"


def _offset(request: QueryRequest) -> int:
    if request.cursor is None:
        return 0
    prefix = f"cp03:{request.query_id}:"
    require(request.cursor.startswith(prefix), "QUERY_CURSOR_IDENTITY")
    suffix = request.cursor[len(prefix):]
    require(suffix.isdigit() and len(suffix) <= 16, "QUERY_CURSOR_OFFSET")
    offset = int(suffix)
    require(is_wire_integer(offset) and offset >= 0, "QUERY_CURSOR_OFFSET")
    return offset


def _state_from_markers(records, markers, *, historical_missing: bool) -> QueryState:
    if any(type(item) is StaleEnvelope for item in markers):
        return QueryState.STALE
    if any(type(item) is PartialEnvelope for item in markers):
        return QueryState.PARTIAL
    unavailable = next((item for item in markers if type(item) is UnavailableEnvelope), None)
    if unavailable is not None:
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


class MissionControlQueryCatalog:
    """Read-only catalog; input records remain truth and CP06 owns persistence."""

    def __init__(self, records: Iterable[WireRecord], *, available: bool = True):
        copied = tuple(records)
        require(all(isinstance(item, WireRecord) for item in copied), "QUERY_RECORD")
        require(type(available) is bool, "QUERY_AVAILABILITY")
        ids = tuple(item.meta.record_id for item in copied)
        require(len(ids) == len(set(ids)), "QUERY_RECORD_ID_DUPLICATE")
        self._records = tuple(sorted(copied, key=_record_sort_key))
        self.available = available
        self._by_id = {item.meta.record_id: item for item in self._records}

    @classmethod
    def unavailable(cls) -> "MissionControlQueryCatalog":
        return cls((), available=False)

    def _base_records(self, request: QueryRequest) -> tuple[WireRecord, ...]:
        record_types = _FAMILY_TYPES.get(request.family)
        require(record_types is not None, "QUERY_FAMILY_RECORDS")
        rows = [item for item in self._records if type(item) in record_types]
        if request.schema_version is not None:
            rows = [item for item in rows if item.schema_version == request.schema_version]
        if request.run_id is not None:
            rows = [item for item in rows if item.meta.run is not None
                    and item.meta.run.run_id == request.run_id]
        if request.record_id is not None:
            rows = [item for item in rows if item.meta.record_id == request.record_id]
        if request.generation is not None:
            rows = [item for item in rows if item.meta.run is not None
                    and item.meta.run.generation == request.generation]
        if request.as_of is not None:
            rows = [item for item in rows if item.meta.as_of == request.as_of]
        if request.frontier_id is not None:
            rows = [item for item in rows if type(item) is CurriculumFrontier
                    and item.frontier_id == request.frontier_id]
        if request.mode is QueryMode.CURRENT and request.record_id is None:
            generations = {}
            for item in rows:
                run = item.meta.run
                if run is not None:
                    generations[run.run_id] = max(
                        run.generation, generations.get(run.run_id, -1))
            if generations:
                rows = [item for item in rows if item.meta.run is not None
                        and item.meta.run.generation == generations[item.meta.run.run_id]]
        return tuple(rows)

    def _markers(self, records, request: QueryRequest) -> tuple[WireRecord, ...]:
        record_ids = {item.meta.record_id for item in records}
        resources = {
            request.family.value,
            request.record_id,
            None if request.run_id is None else f"{request.family.value}:{request.run_id}",
        }
        markers = [
            item for item in self._records
            if ((type(item) is PartialEnvelope and item.partial_record_id in record_ids)
                or (type(item) is StaleEnvelope and item.stale_record_id in record_ids))
                or (type(item) is UnavailableEnvelope and item.resource in resources)
        ]
        if not records and request.as_of is not None:
            markers.extend(
                item for item in self._records
                if type(item) is StaleEnvelope
                and item.requested_as_of == request.as_of
                and item.stale_record_id in self._by_id
                and type(self._by_id[item.stale_record_id])
                in _FAMILY_TYPES.get(request.family, ())
            )
        return tuple(sorted(markers, key=_record_sort_key))

    def _links_for(self, record: WireRecord) -> tuple[QueryLink, ...]:
        links = []
        meta = record.meta
        for relation, refs in (
            ("SOURCE", meta.source_refs),
            ("EVIDENCE", meta.evidence_refs),
            ("RECEIPT", meta.receipt_refs),
        ):
            links.extend(QueryLink(
                relation, meta.record_id, ref,
                ref if ref in self._by_id else None,
            ) for ref in refs)
        if type(record) is OperatorView:
            links.extend(QueryLink(
                "RELATED_RECORD", meta.record_id, ref,
                ref if ref in self._by_id else None,
            ) for ref in record.related_record_ids)
        if type(record) is CapabilitySnapshot and meta.run is not None:
            for item in self._records:
                if (type(item) is LearningEpisode and item.meta.run == meta.run
                        and item.capability_id == record.capability_id):
                    links.append(QueryLink(
                        "EPISODE", meta.record_id, item.meta.record_id,
                        item.meta.record_id))
        if type(record) is GenerationManifest:
            links.append(QueryLink(
                "CHECKPOINT", meta.record_id,
                f"checkpoint:{record.checkpoint_sha256}"))
        return tuple(sorted(
            links, key=lambda item: (
                item.relation, item.target_ref, item.source_record_id)))

    def _query_links(self, request: QueryRequest) -> QueryPage:
        record = self._by_id.get(request.record_id)
        links = () if record is None else self._links_for(record)
        return self._page(request, (), (), links, exact_missing=record is None)

    def _query_reference(self, request: QueryRequest) -> QueryPage:
        links = tuple(
            link for record in self._records for link in self._links_for(record)
            if link.target_ref == request.reference
        )
        return self._page(request, (), (), links, exact_missing=not links)

    def _page(self, request, records, markers, links=(), *, exact_missing=False):
        rows = links if request.family in {QueryFamily.LINKS, QueryFamily.REFERENCE} else records
        offset = _offset(request)
        require(offset <= len(rows), "QUERY_CURSOR_RANGE")
        page_rows = rows[offset:offset + request.limit]
        next_offset = offset + len(page_rows)
        next_cursor = _cursor(request, next_offset) if next_offset < len(rows) else None
        page_records = tuple(page_rows) if rows is records else ()
        page_links = tuple(page_rows) if rows is links else ()
        page_ids = {item.meta.record_id for item in page_records}
        page_markers = tuple(
            item for item in markers
            if ((type(item) is PartialEnvelope and item.partial_record_id in page_ids)
                or (type(item) is StaleEnvelope
                    and (item.stale_record_id in page_ids or not records))
                or type(item) is UnavailableEnvelope)
        )
        state = (
            QueryState.UNAVAILABLE if not self.available
            else _state_from_markers(
                page_records, page_markers,
                historical_missing=(
                    exact_missing or request.mode is QueryMode.HISTORICAL),
            )
        )
        if page_links:
            state = QueryState.PRESENT
        coverage = (
            CoverageState.UNKNOWN if state in {
                QueryState.MISSING, QueryState.UNAVAILABLE,
                QueryState.DENIED, QueryState.UNKNOWN,
            }
            else CoverageState.PARTIAL if (
                state in {QueryState.PARTIAL, QueryState.STALE}
                or next_cursor is not None)
            else CoverageState.COMPLETE
        )
        return QueryPage(
            request=request, state=state, coverage=coverage,
            total_matches=len(rows), records=page_records,
            markers=page_markers, links=page_links,
            next_cursor=next_cursor,
        )

    def query(self, request: QueryRequest) -> QueryPage:
        if request.family is QueryFamily.LINKS:
            return self._query_links(request)
        if request.family is QueryFamily.REFERENCE:
            return self._query_reference(request)
        if not self.available:
            return self._page(request, (), (), exact_missing=False)
        records = self._base_records(request)
        markers = self._markers(records, request)
        exact_missing = bool(
            request.record_id is not None
            or request.generation is not None
            or request.frontier_id is not None
            or request.as_of is not None
        ) and not records and not markers
        return self._page(
            request, records, markers, exact_missing=exact_missing)

    @staticmethod
    def encode_page(page: QueryPage) -> dict:
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
