"""Strict source-proposal serialization rejects forged equality/types."""
from __future__ import annotations
from dataclasses import fields, is_dataclass
import json
from bilqis_mlx.semantics.atlas_projection import CorpusCoverageRow, SourceLocus, SourceRecordRef
from .common import _fail

def _strict_source_primitive(value: object) -> object:
    """Reject custom equality, dataclass subclasses and tuple subclasses."""
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is tuple:
        return [_strict_source_primitive(item) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            _fail("BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE")
        return {key: _strict_source_primitive(item)
                for key, item in value.items()}
    from .adapters import SourceFamilyAdapter
    from .types import (ConceptFamilyCoverage, FamilyObligation,
        FamilyInventoryCounts, SemanticFamilyInventory)
    from .curriculum import LearnedFrontier, CurriculumCandidateSet
    from .lesson_types import SourceConstructiveLesson, SourceConstructiveLessonSet
    allowed = {
        CorpusCoverageRow, SourceLocus, SourceRecordRef,
        ConceptFamilyCoverage, FamilyObligation, FamilyInventoryCounts,
        SemanticFamilyInventory, SourceFamilyAdapter, LearnedFrontier,
        CurriculumCandidateSet, SourceConstructiveLesson,
        SourceConstructiveLessonSet,
    }
    if is_dataclass(value) and type(value) in allowed:
        return {field.name: _strict_source_primitive(getattr(value, field.name))
                for field in fields(value)}
    _fail("BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE")


def _strict_source_bytes(value: object) -> bytes:
    return (json.dumps(
        _strict_source_primitive(value), sort_keys=True,
        ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")
