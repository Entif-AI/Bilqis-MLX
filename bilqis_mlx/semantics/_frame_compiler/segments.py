"""Segments for causal source-prefix compilation."""
from __future__ import annotations
from .. import frame_compiler as _facade
from dataclasses import dataclass

from ..frame_schema import SourceSpan
from .batch import CompiledFrameBatch
from .contracts import LAWFUL_SEGMENT_SCHEMA, COMPILED_SEGMENTS_SCHEMA, BOUNDARY_EVIDENCE_SCHEMA, MAX_NEURAL_POSITIONS
from .source import StreamingAST, FrameCompilerConfig



@dataclass(frozen=True)
class LawfulSourceSegment:
    """Source-adapter-declared segment, not an arbitrary compiler cut."""
    origin_source_id: str
    global_span: SourceSpan
    boundary_source_handle: str
    ast: StreamingAST
    config: FrameCompilerConfig
    schema_version: str = LAWFUL_SEGMENT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.origin_source_id, str)
                or not self.origin_source_id
                or not isinstance(self.global_span, SourceSpan)
                or self.global_span.end <= self.global_span.start
                or not isinstance(self.ast, StreamingAST)
                or self.global_span.end - self.global_span.start
                != len(self.ast.atoms)
                or not isinstance(self.boundary_source_handle, str)
                or not self.boundary_source_handle
                or not isinstance(self.config, FrameCompilerConfig)
                or self.schema_version != LAWFUL_SEGMENT_SCHEMA):
            _facade._invalid("BAMF_PREFIX_LAWFUL_SEGMENT_INVALID")



def boundary_evidence_digest(segment: LawfulSourceSegment) -> str:
    """Source-adapter evidence identity for a declared lawful split."""
    if not isinstance(segment, LawfulSourceSegment):
        _facade._invalid("BAMF_PREFIX_SPLIT_INPUT_INVALID")
    return _facade.contract_digest((
        BOUNDARY_EVIDENCE_SCHEMA, segment.origin_source_id,
        segment.global_span.start, segment.global_span.end,
        segment.ast.source_instance_id, segment.boundary_source_handle))



@dataclass(frozen=True)
class CompiledFrameSegments:
    origin_source_id: str
    global_spans: tuple[SourceSpan, ...]
    boundary_source_handles: tuple[str, ...]
    segments: tuple[CompiledFrameBatch, ...]
    total_source_atoms: int
    total_neural_positions: int
    schema_version: str = COMPILED_SEGMENTS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.origin_source_id, str)
                or not self.origin_source_id
                or not isinstance(self.global_spans, tuple)
                or not isinstance(self.boundary_source_handles, tuple)
                or not isinstance(self.segments, tuple)
                or not (len(self.global_spans)
                        == len(self.boundary_source_handles)
                        == len(self.segments))
                or any(not isinstance(item, CompiledFrameBatch)
                       for item in self.segments)
                or any(not isinstance(span, SourceSpan)
                       for span in self.global_spans)
                or any(not isinstance(handle, str) or not handle
                       for handle in self.boundary_source_handles)
                or len(set(self.boundary_source_handles))
                != len(self.boundary_source_handles)
                or any(span.end - span.start != segment.visible_end
                       for span, segment in zip(
                           self.global_spans, self.segments))
                or any(span.start != (
                    self.global_spans[index - 1].end if index else 0)
                    for index, span in enumerate(self.global_spans))
                or any(len(item.positions) > MAX_NEURAL_POSITIONS
                       for item in self.segments)
                or type(self.total_source_atoms) is not int
                or self.total_source_atoms != sum(
                    item.visible_end for item in self.segments)
                or type(self.total_neural_positions) is not int
                or self.total_neural_positions != sum(
                    len(item.positions) for item in self.segments)
                or self.schema_version != COMPILED_SEGMENTS_SCHEMA):
            _facade._invalid("BAMF_PREFIX_COMPILED_SEGMENTS_INVALID")



def compile_lawful_segments(
    segments: tuple[LawfulSourceSegment, ...], release: str,
) -> CompiledFrameSegments:
    """Compile only source-declared contiguous boundaries, never truncate."""
    if (not isinstance(segments, tuple) or not segments
            or any(not isinstance(item, LawfulSourceSegment)
                   for item in segments)):
        _facade._invalid("BAMF_PREFIX_SPLIT_INPUT_INVALID")
    origin = segments[0].origin_source_id
    authority = _facade._segment_authority(segments[0].config)
    cursor = 0
    handles = set()
    for segment in segments:
        if (segment.origin_source_id != origin
                or segment.global_span.start != cursor
                or segment.boundary_source_handle in handles
                or _facade._segment_authority(segment.config) != authority):
            _facade._invalid("BAMF_PREFIX_SPLIT_BOUNDARY_INVALID")
        cursor = segment.global_span.end
        handles.add(segment.boundary_source_handle)
        grant = next((
            item for item in segment.config.frontier.grants
            if item.source_handle == segment.boundary_source_handle
        ), None)
        if not _facade._grant_allows(
                grant, _facade.boundary_evidence_digest(segment),
                segment.config, release):
            _facade._invalid("BAMF_PREFIX_SPLIT_SOURCE_UNAUTHORIZED")
        if len(segment.ast.atoms) > MAX_NEURAL_POSITIONS:
            _facade._invalid("BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")
        approved = (
            {item.frame.occurrence_id: item
             for item in segment.config.approved.envelopes}
            if segment.config.approved is not None else {})
        closed = _facade._source_frames(
            segment.ast, len(segment.ast.atoms), approved)
        if len(segment.ast.atoms) + len(closed) > MAX_NEURAL_POSITIONS:
            _facade._invalid("BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")

    compiled = tuple(
        _facade.compile_prefix(
            segment.ast, len(segment.ast.atoms), release, segment.config)
        for segment in segments)
    return CompiledFrameSegments(
        origin, tuple(item.global_span for item in segments),
        tuple(item.boundary_source_handle for item in segments),
        compiled, cursor, sum(len(item.positions) for item in compiled))
