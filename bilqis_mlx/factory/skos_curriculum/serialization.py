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

def _exact_record(record, cls):
    expected = {field.name for field in fields(cls)}
    if not isinstance(record, dict) or set(record) != expected:
        _fail("BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE")
    return record


def _tuple_strings(value):
    if not isinstance(value, list) or any(type(item) is not str for item in value):
        _fail("BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE")
    return tuple(value)


def _coverage_row(record):
    _exact_record(record, CorpusCoverageRow)
    return CorpusCoverageRow(**record)


def curriculum_candidate_from_bytes(raw: bytes):
    """Decode only the exact canonical CurriculumCandidateSet record shape."""
    if type(raw) is not bytes:
        _fail("BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE")
    try:
        record = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE")
    from .curriculum import CurriculumCandidateSet
    from .lesson_types import SourceConstructiveLesson
    from .types import (
        ConceptFamilyCoverage, FamilyInventoryCounts, FamilyObligation,
        SemanticFamilyInventory,
    )
    record = _exact_record(record, CurriculumCandidateSet)
    census_record = _exact_record(record["census"], SemanticFamilyInventory)
    concepts = tuple(ConceptFamilyCoverage(
        **{**_exact_record(item, ConceptFamilyCoverage),
           "required_family_ids": _tuple_strings(item["required_family_ids"]),
           "source_refs": _tuple_strings(item["source_refs"])})
        for item in census_record["concepts"])
    obligations = tuple(FamilyObligation(**_exact_record(item, FamilyObligation))
                        for item in census_record["obligations"])
    source_nonconcept = tuple(
        (_coverage_row(pair[0]), _tuple_strings(pair[1]))
        for pair in census_record["source_nonconcept"]
        if isinstance(pair, list) and len(pair) == 2)
    if len(source_nonconcept) != len(census_record["source_nonconcept"]):
        _fail("BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE")
    census = SemanticFamilyInventory(
        semantic_release=census_record["semantic_release"],
        atlas_bundle_id=census_record["atlas_bundle_id"],
        source_bundle_id=census_record["source_bundle_id"],
        source_coverage_sha256=census_record["source_coverage_sha256"],
        source_eligible_concept_ids=_tuple_strings(
            census_record["source_eligible_concept_ids"]),
        required_source_family_ids=_tuple_strings(
            census_record["required_source_family_ids"]),
        pending_source_family_ids=_tuple_strings(
            census_record["pending_source_family_ids"]),
        concepts=concepts,
        obligations=obligations,
        source_held=tuple(_coverage_row(item) for item in census_record["source_held"]),
        source_ir_only=tuple(
            _coverage_row(item) for item in census_record["source_ir_only"]),
        source_nonconcept=source_nonconcept,
        counts=FamilyInventoryCounts(**_exact_record(
            census_record["counts"], FamilyInventoryCounts)),
        source_authority=census_record["source_authority"],
        schema=census_record["schema"],
    )
    lessons = tuple(SourceConstructiveLesson(
        **{**_exact_record(item, SourceConstructiveLesson),
           "positive_fact": _tuple_strings(item["positive_fact"]),
           "contrast_fact": _tuple_strings(item["contrast_fact"]),
           "constituents": _tuple_strings(item["constituents"]),
           "prerequisite_closure": _tuple_strings(item["prerequisite_closure"]),
           "variation_axes": _tuple_strings(item["variation_axes"])})
        for item in record["source_lessons"])
    candidate = CurriculumCandidateSet(
        census=census,
        source_adapter_ids=_tuple_strings(record["source_adapter_ids"]),
        unverified_exposure_claims=_tuple_strings(
            record["unverified_exposure_claims"]),
        unverified_qualification_claims=_tuple_strings(
            record["unverified_qualification_claims"]),
        source_lessons=lessons,
        learning_state=record["learning_state"],
        adapter_ready_count=record["adapter_ready_count"],
        exposed_count=record["exposed_count"],
        qualified_count=record["qualified_count"],
        status=record["status"],
        source_authority=record["source_authority"],
        schema=record["schema"],
    )
    if _strict_source_bytes(candidate) != raw:
        _fail("BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE")
    return candidate
