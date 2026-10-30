"""A08.1b.4 source-attested scope/modality contrasts, without admission.

Only exact A01 source notations are represented here. A grammar-category
label does not prove a contextual transformation, and no A13 grant is minted.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from bilqis_mlx.semantics.atlas_projection import (
    CorpusCoverageRow, FrozenAtlasSnapshot,
)
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)

from .common import _fail
from .inventory import _grammar_category, _inventory_source_families


_GRAMMAR_CODE = "https://github.com/Entif-AI/Bilqis-MLX/id/datatype/grammar-code"
_SURFACE_FORM = "https://github.com/Entif-AI/Bilqis-MLX/id/datatype/new-ithkuil"
_SCHEMA = "bilqis.scope-source-contrast-proposal/v1"
_STATUS = "SOURCE_NOTATION_NOT_CONTEXTUAL_LAW"
_DEBT_SCHEMA = "bilqis.scope-source-implementation-debt/v1"


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceScopeContrast:
    """One exact scope/modality source value and a different same-category value."""

    semantic_release: str
    atlas_bundle_id: str
    semantic_id: str
    source_row: str
    category: str
    grammar_code: str
    surface_form: str
    contrast_semantic_id: str
    contrast_grammar_code: str
    contrast_surface_form: str
    source_evidence_sha256: str
    status: str = _STATUS
    schema: str = _SCHEMA

    def __post_init__(self) -> None:
        values = (
            self.semantic_id, self.source_row, self.category,
            self.grammar_code, self.surface_form,
            self.contrast_semantic_id, self.contrast_grammar_code,
            self.contrast_surface_form,
        )
        if (any(type(item) is not str or not item for item in values)
                or self.semantic_id == self.contrast_semantic_id
                or any(type(item) is not str or len(item) != 64
                       or any(char not in "0123456789abcdef" for char in item)
                       for item in (
                           self.semantic_release, self.atlas_bundle_id,
                           self.source_evidence_sha256))
                or self.status != _STATUS or self.schema != _SCHEMA):
            _fail("BAMF_SCOPE_SOURCE_CONTRAST_INVALID")


@dataclass(frozen=True)
class SourceScopeDebtLedger:
    """Preserve A01 source holds and unadmitted transformation row identities."""

    semantic_release: str
    source_held_atomic_rows: tuple[CorpusCoverageRow, ...]
    nonconcept_transformations: tuple[CorpusCoverageRow, ...]
    status: str = "IMPLEMENTATION_UNCOVERED"
    schema: str = _DEBT_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.semantic_release) is not str
                or len(self.semantic_release) != 64
                or any(ch not in "0123456789abcdef"
                       for ch in self.semantic_release)
                or any(type(row) is not CorpusCoverageRow
                       or (row.domain, row.table,
                           row.source_disposition) != (
                               "atomic", "morphemes_atomic", "SOURCE_HELD")
                       for row in self.source_held_atomic_rows)
                or any(type(row) is not CorpusCoverageRow
                       or (row.domain, row.table,
                           row.source_disposition) != (
                               "residue", "allomorph_rules",
                               "SOURCE_EMITTED_NON_CONCEPT")
                       for row in self.nonconcept_transformations)
                or self.status != "IMPLEMENTATION_UNCOVERED"
                or self.schema != _DEBT_SCHEMA):
            _fail("BAMF_SCOPE_SOURCE_DEBT_LEDGER_INVALID")


def _source_realizations(concept) -> tuple[str, str] | None:
    by_type = {}
    for notation in concept.realizations:
        if notation.datatype in (_GRAMMAR_CODE, _SURFACE_FORM):
            by_type.setdefault(notation.datatype, set()).add(notation.value)
    if (len(by_type.get(_GRAMMAR_CODE, ())) != 1
            or len(by_type.get(_SURFACE_FORM, ())) != 1):
        return None
    return (next(iter(by_type[_GRAMMAR_CODE])),
            next(iter(by_type[_SURFACE_FORM])))


def _source_scope_contrasts(
    snapshot: FrozenAtlasSnapshot,
) -> tuple[tuple[SourceScopeContrast, ...], tuple[str, ...]]:
    """Derive source identity contrasts; keep every unsupported family visible."""
    census = _inventory_source_families(snapshot)
    concepts = {item.concept.semantic_id: item.concept
                for item in snapshot.concepts}
    grouped: dict[str, list[tuple[str, str, str, str]]] = {}
    for obligation in census.obligations:
        if obligation.family_id != "scope_modality_time":
            continue
        concept = concepts.get(obligation.semantic_id)
        if concept is None or len(concept.source_rows) != 1:
            continue
        category = _grammar_category(obligation.semantic_id)
        realizations = _source_realizations(concept)
        if category is None or realizations is None:
            continue
        row = concept.source_rows[0]
        if (row.domain, row.table) != ("atomic", "morphemes_atomic"):
            continue
        grouped.setdefault(category, []).append((
            obligation.semantic_id, f"{row.domain}/{row.table}/{row.key}",
            *realizations))
    lessons = []
    for category, group in sorted(grouped.items()):
        group.sort()
        if len(group) < 2:
            continue
        for index, (semantic_id, source_row, code, surface) in enumerate(group):
            contrast_id, _, contrast_code, contrast_surface = (
                group[(index + 1) % len(group)])
            evidence = _digest((
                _SCHEMA, snapshot.release_sha256, snapshot.bundle_id,
                semantic_id, source_row, category, code, surface,
                contrast_id, contrast_code, contrast_surface,
            ))
            lessons.append(SourceScopeContrast(
                snapshot.release_sha256, snapshot.bundle_id,
                semantic_id, source_row, category, code, surface,
                contrast_id, contrast_code, contrast_surface, evidence))
    covered = {lesson.semantic_id for lesson in lessons}
    uncovered = tuple(sorted(
        obligation.semantic_id for obligation in census.obligations
        if obligation.family_id == "scope_modality_time"
        and obligation.semantic_id not in covered))
    return tuple(sorted(lessons, key=lambda item: item.semantic_id)), uncovered


def source_scope_contrasts(
    selection: AtlasArtifactSelection,
) -> tuple[tuple[SourceScopeContrast, ...], tuple[str, ...]]:
    """Rebuild from independently pinned source, never caller-supplied records."""
    return _source_scope_contrasts(load_pinned_atlas_snapshot(selection))


def source_scope_debt(selection: AtlasArtifactSelection) -> SourceScopeDebtLedger:
    """Report source-held atomic rows and transformation rows without IDs.

    An atomic row held for a notation collision is not presumed to be a
    scope/mood row. A nonconcept allomorph record cannot be an executable
    transformation until a separately governed semantic identity exists.
    """
    snapshot = load_pinned_atlas_snapshot(selection)
    census = _inventory_source_families(snapshot)
    held = tuple(row for row in census.source_held
                 if (row.domain, row.table)
                 == ("atomic", "morphemes_atomic"))
    nonconcept = tuple(row for row, families in census.source_nonconcept
                       if "released_transformations" in families)
    return SourceScopeDebtLedger(snapshot.release_sha256, held, nonconcept)


def check_scope_contrast(
    lesson: SourceScopeContrast, answer: object,
    selection: AtlasArtifactSelection,
) -> bool:
    """Check actual source identity, not lesson-supplied correct-answer labels."""
    if type(lesson) is not SourceScopeContrast:
        _fail("BAMF_SCOPE_SOURCE_CONTRAST_INVALID")
    SourceScopeContrast.__post_init__(lesson)
    expected, _ = source_scope_contrasts(selection)
    matching = tuple(item for item in expected
                     if item.semantic_id == lesson.semantic_id)
    if len(matching) != 1 or matching[0] != lesson:
        _fail("BAMF_SCOPE_SOURCE_PROJECTION_DRIFT")
    return type(answer) is str and answer == matching[0].semantic_id
