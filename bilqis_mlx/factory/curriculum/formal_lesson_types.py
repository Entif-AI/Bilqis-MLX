"""Immutable task-scoped formal lesson contract types."""
from __future__ import annotations

from dataclasses import dataclass
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.cognitive_operators import TypedValue, ValueState, VALUE_SCHEMA

FORMAL_LESSON_SCHEMA = "bilqis.formal-constructive-lesson-proposal/v1"
FORMAL_LESSON_STATUS = "TASK_SCOPED_NOT_ADMITTED"
SOURCE_PROJECTION_ONLY = "SOURCE_PROJECTION_NOT_AUTHORITY"
LEARNING_UNVERIFIED = "LEARNING_UNVERIFIED"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SUPPORTED = frozenset({"BOOL_NOT", "BOOL_AND", "COUNT", "SUCC"})
FORMAL_VARIATION_AXES = {
    "BOOL_NOT": ("boolean-input-polarity", "typed-answer-contrast"),
    "BOOL_AND": ("boolean-pair-combinations", "typed-answer-contrast"),
    "COUNT": ("entity-set-cardinality", "typed-answer-contrast"),
    "SUCC": ("numeric-successor-input", "typed-answer-contrast"),
}


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _typed_exact(value: object) -> bool:
    """Accept only the released primitive input/output shapes for this leaf."""
    if (type(value) is not TypedValue
            or type(value.type_name) is not str
            or type(value.semantic_release) is not str
            or not _SHA.fullmatch(value.semantic_release)
            or type(value.state) is not ValueState
            or value.state is not ValueState.VALUE
            or (value.source_handle is not None
                and (type(value.source_handle) is not str
                     or not value.source_handle))
            or type(value.schema_version) is not str
            or value.schema_version != VALUE_SCHEMA):
        return False
    if value.type_name == "Boolean":
        return type(value.value) is bool
    if value.type_name == "Number":
        return type(value.value) is int
    if value.type_name == "EntitySet":
        return (type(value.value) is tuple
                and all(type(item) is str and bool(item)
                        for item in value.value)
                and value.value == tuple(sorted(set(value.value))))
    return False


@dataclass(frozen=True)
class FormalConstructiveLesson:
    semantic_release: str
    atlas_bundle_id: str
    semantic_id: str
    operator_id: str
    source_binding_sha256: str
    operator_grant_sha256: str
    typed_inputs: tuple[TypedValue, ...]
    operand_evidence_sha256: tuple[str, ...]
    positive: TypedValue
    contrast: TypedValue
    constituents: tuple[str, ...]
    prerequisite_closure: tuple[str, ...]
    variation_axes: tuple[str, ...]
    evidence_sha256: str
    status: str = FORMAL_LESSON_STATUS
    source_authority: str = SOURCE_PROJECTION_ONLY
    learning_state: str = LEARNING_UNVERIFIED
    schema: str = FORMAL_LESSON_SCHEMA

    def __post_init__(self) -> None:
        if (any(type(value) is not str or not _SHA.fullmatch(value)
                for value in (
                    self.semantic_release, self.atlas_bundle_id,
                    self.source_binding_sha256, self.operator_grant_sha256,
                    self.evidence_sha256))
                or type(self.semantic_id) is not str or not self.semantic_id
                or type(self.operator_id) is not str or self.operator_id not in _SUPPORTED
                or type(self.typed_inputs) is not tuple or not self.typed_inputs
                or any(not _typed_exact(item) for item in self.typed_inputs)
                or type(self.operand_evidence_sha256) is not tuple
                or len(self.operand_evidence_sha256) != len(self.typed_inputs)
                or any(type(item) is not str or not _SHA.fullmatch(item)
                       for item in self.operand_evidence_sha256)
                or not _typed_exact(self.positive)
                or not _typed_exact(self.contrast)
                or self.positive.type_name != self.contrast.type_name
                or self.positive.semantic_release != self.semantic_release
                or self.contrast.semantic_release != self.semantic_release
                or self.positive.source_handle is not None
                or self.contrast.source_handle is not None
                or type(self.constituents) is not tuple
                or type(self.prerequisite_closure) is not tuple
                or type(self.variation_axes) is not tuple
                or self.variation_axes != FORMAL_VARIATION_AXES[self.operator_id]
                or any(type(item) is not str or not item
                       for group in (
                           self.constituents, self.prerequisite_closure,
                           self.variation_axes) for item in group)
                or self.positive.value == self.contrast.value
                or type(self.status) is not str
                or self.status != FORMAL_LESSON_STATUS
                or type(self.source_authority) is not str
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or type(self.learning_state) is not str
                or self.learning_state != LEARNING_UNVERIFIED
                or type(self.schema) is not str
                or self.schema != FORMAL_LESSON_SCHEMA):
            _fail("BAMF_FORMAL_LESSON_INVALID")
