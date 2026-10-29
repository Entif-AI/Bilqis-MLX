"""Unverified A08 candidate bridge and source-replay assertion."""
from __future__ import annotations
from dataclasses import dataclass
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot, CorpusCoverageRow
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from .adapters import SourceFamilyAdapter, SOURCE_FAMILY_ADAPTERS
from .common import (_fail, _SHA, _load_pinned, LEARNED_FRONTIER_SCHEMA,
    CURRICULUM_CANDIDATE_SCHEMA, LEARNING_UNVERIFIED, SOURCE_PROJECTION_ONLY)
from .inventory import _inventory_source_families
from .lesson_compiler import _compile_source_constructive_lessons_snapshot
from .lesson_types import SourceConstructiveLesson
from .serialization import _strict_source_bytes
from .types import FamilyObligation, SemanticFamilyInventory

@dataclass(frozen=True)
class LearnedFrontier:
    """Unverified learner claims; source eligibility never depends on them."""

    semantic_release: str
    claimed_exposed: tuple[str, ...] = ()
    claimed_qualified: tuple[str, ...] = ()
    schema: str = LEARNED_FRONTIER_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or any(not isinstance(group, tuple)
                       or group != tuple(sorted(set(group)))
                       or any(not isinstance(item, str) or not item
                              for item in group)
                       for group in (
                           self.claimed_exposed, self.claimed_qualified))
                or self.schema != LEARNED_FRONTIER_SCHEMA):
            _fail("BAMF_FAMILY_LEARNED_FRONTIER_INVALID")


@dataclass(frozen=True)
class CurriculumCandidateSet:
    """A08.1a census-only bridge; A08.1b owns constructive readiness."""

    census: SemanticFamilyInventory
    source_adapter_ids: tuple[str, ...]
    unverified_exposure_claims: tuple[str, ...]
    unverified_qualification_claims: tuple[str, ...]
    source_lessons: tuple["SourceConstructiveLesson", ...] = ()
    learning_state: str = LEARNING_UNVERIFIED
    adapter_ready_count: int = 0
    exposed_count: int = 0
    qualified_count: int = 0
    status: str = "IMPLEMENTATION_DEBT"
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = CURRICULUM_CANDIDATE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.census, SemanticFamilyInventory)
                or self.source_adapter_ids
                != tuple(sorted(set(self.source_adapter_ids)))
                or not isinstance(self.source_lessons, tuple)
                or any(not isinstance(item, SourceConstructiveLesson)
                       or item.semantic_release != self.census.semantic_release
                       for item in self.source_lessons)
                or self.learning_state != LEARNING_UNVERIFIED
                or any(value != 0 for value in (
                    self.adapter_ready_count, self.exposed_count,
                    self.qualified_count))
                or self.status != "IMPLEMENTATION_DEBT"
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != CURRICULUM_CANDIDATE_SCHEMA):
            _fail("BAMF_FAMILY_CANDIDATE_SET_INVALID")

    @property
    def semantic_release(self) -> str:
        return self.census.semantic_release

    @property
    def atlas_bundle_id(self) -> str:
        return self.census.atlas_bundle_id

    @property
    def source_eligible_concept_ids(self) -> tuple[str, ...]:
        return self.census.source_eligible_concept_ids

    @property
    def required_source_family_ids(self) -> tuple[str, ...]:
        return self.census.required_source_family_ids

    @property
    def coverage_rows(self) -> tuple[FamilyObligation, ...]:
        return self.census.obligations

    @property
    def source_hold_rows(self) -> tuple[CorpusCoverageRow, ...]:
        return self.census.source_held

    @property
    def source_held_count(self) -> int:
        return self.census.counts.source_held_rows

    @property
    def implementation_uncovered_count(self) -> int:
        return self.census.counts.implementation_uncovered_obligations

    @property
    def frozen_census_digest(self) -> str:
        return self.census.digest

    @property
    def source_lesson_count(self) -> int:
        return len(self.source_lessons)


def _compile_semantic_curriculum_snapshot(
    atlas: FrozenAtlasSnapshot,
    source_adapters: tuple[SourceFamilyAdapter, ...],
    learned_frontier: LearnedFrontier,
) -> CurriculumCandidateSet:
    """Original A08 owner API, staged without constructor/learning promotion."""
    census = _inventory_source_families(atlas)
    if (not isinstance(source_adapters, tuple)
            or any(not isinstance(item, SourceFamilyAdapter)
                   or item not in SOURCE_FAMILY_ADAPTERS
                   for item in source_adapters)
            or len(set(item.family_id for item in source_adapters))
            != len(source_adapters)
            or not isinstance(learned_frontier, LearnedFrontier)
            or learned_frontier.semantic_release != census.semantic_release):
        _fail("BAMF_FAMILY_COMPILER_INPUT_INVALID")
    return CurriculumCandidateSet(
        census=census,
        source_adapter_ids=tuple(sorted(
            item.family_id for item in source_adapters)),
        unverified_exposure_claims=learned_frontier.claimed_exposed,
        unverified_qualification_claims=learned_frontier.claimed_qualified,
        source_lessons=_compile_source_constructive_lessons_snapshot(
            atlas, census=census).lessons)


def compile_semantic_curriculum(
    atlas: AtlasArtifactSelection,
    source_adapters: tuple[SourceFamilyAdapter, ...],
    learned_frontier: LearnedFrontier,
) -> CurriculumCandidateSet:
    """Original three-argument API with an A01-pinned source authority."""
    return _compile_semantic_curriculum_snapshot(
        _load_pinned(atlas), source_adapters, learned_frontier)


def assert_curriculum_candidate_current(
    candidate: CurriculumCandidateSet,
    atlas: AtlasArtifactSelection,
    learned_frontier: LearnedFrontier,
) -> None:
    """Replay A01 with the code-owned adapter registry, never caller adapters."""
    if (type(candidate) is not CurriculumCandidateSet
            or type(learned_frontier) is not LearnedFrontier
            or _strict_source_bytes(candidate)
            != _strict_source_bytes(compile_semantic_curriculum(
                atlas, SOURCE_FAMILY_ADAPTERS, learned_frontier))):
        _fail("BAMF_CANDIDATE_SOURCE_PROJECTION_DRIFT")
