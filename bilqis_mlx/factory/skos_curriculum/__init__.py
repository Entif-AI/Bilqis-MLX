"""A01 source-qualified A08 family inventory and constructive proposals."""
from bilqis_mlx.semantics.atlas_snapshot import load_pinned_atlas_snapshot
from .common import (FAMILY_INVENTORY_SCHEMA, FAMILY_OBLIGATION_SCHEMA,
    FAMILY_CONCEPT_SCHEMA, FAMILY_RULE_SCHEMA, CURRICULUM_CANDIDATE_SCHEMA,
    LEARNED_FRONTIER_SCHEMA, SOURCE_LESSON_SCHEMA, SOURCE_LESSON_SET_SCHEMA,
    LEARNING_UNVERIFIED, SOURCE_PROJECTION_ONLY)
from .adapters import SourceFamilyAdapter, SOURCE_FAMILY_ADAPTERS
from .types import (ConceptFamilyCoverage, FamilyObligation,
    FamilyInventoryCounts, SemanticFamilyInventory)
from .lesson_types import SourceConstructiveLesson, SourceConstructiveLessonSet
from .inventory import (inventory_source_families, assert_family_inventory_current,
    _inventory_source_families)
from .lesson_compiler import (_compile_source_constructive_lessons_snapshot,
    _source_lesson_evidence)
from .curriculum import (LearnedFrontier, CurriculumCandidateSet,
    compile_semantic_curriculum, assert_curriculum_candidate_current,
    _compile_semantic_curriculum_snapshot)
from .checkers import (compile_source_constructive_lessons,
    assert_source_lesson_set_current, check_source_constructive_lesson,
    _check_source_constructive_lesson_snapshot)

__all__ = [
    "SOURCE_FAMILY_ADAPTERS", "SourceFamilyAdapter", "SemanticFamilyInventory",
    "ConceptFamilyCoverage", "FamilyObligation", "FamilyInventoryCounts",
    "LearnedFrontier", "CurriculumCandidateSet", "SourceConstructiveLesson",
    "SourceConstructiveLessonSet", "inventory_source_families",
    "assert_family_inventory_current", "compile_semantic_curriculum",
    "assert_curriculum_candidate_current", "compile_source_constructive_lessons",
    "assert_source_lesson_set_current", "check_source_constructive_lesson",
]
