"""Priority queue contracts for lazy correction revalidation."""
from __future__ import annotations

from dataclasses import dataclass

from ..semantics.cognitive_dependencies import (
    ArtifactNode,
    DependencyIndex,
    DependencyRef,
)
from .atlas_revalidation_common import (
    MAX_REVALIDATION_PRIORITY,
    REVALIDATION_PROGRESS_SCHEMA,
    REVALIDATION_QUEUE_SCHEMA,
    REVALIDATION_TASK_SCHEMA,
    _invalid,
    _name,
)
from .atlas_revalidation_evidence import CorrectionEvent, StateTransition


@dataclass(frozen=True)
class RevalidationTask:
    artifact_id: str
    exigency: int
    impact: int
    cause: DependencyRef
    schema_version: str = REVALIDATION_TASK_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.artifact_id)
                or any(type(value) is not int
                       or not 0 <= value <= MAX_REVALIDATION_PRIORITY
                       for value in (self.exigency, self.impact))
                or not isinstance(self.cause, DependencyRef)
                or self.schema_version != REVALIDATION_TASK_SCHEMA):
            _invalid("BAMF_C09_REVALIDATION_TASK_INVALID")


def _sort_tasks(tasks: tuple[RevalidationTask, ...]) -> tuple[RevalidationTask, ...]:
    return tuple(sorted(
        tasks,
        key=lambda task: (-task.exigency, -task.impact, task.artifact_id),
    ))


@dataclass(frozen=True)
class RevalidationQueue:
    event: CorrectionEvent
    pending: tuple[RevalidationTask, ...]
    held_artifact_ids: tuple[str, ...]
    history: tuple[StateTransition, ...] = ()
    schema_version: str = REVALIDATION_QUEUE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.event, CorrectionEvent)
                or not isinstance(self.pending, tuple)
                or any(not isinstance(task, RevalidationTask)
                       for task in self.pending)
                or self.pending != _sort_tasks(self.pending)
                or len({task.artifact_id for task in self.pending})
                != len(self.pending)
                or self.held_artifact_ids != tuple(
                    sorted(task.artifact_id for task in self.pending))
                or not isinstance(self.history, tuple)
                or any(not isinstance(item, StateTransition)
                       for item in self.history)
                or self.schema_version != REVALIDATION_QUEUE_SCHEMA):
            _invalid("BAMF_C09_REVALIDATION_QUEUE_INVALID")


@dataclass(frozen=True)
class RevalidationProgress:
    index: DependencyIndex
    queue: RevalidationQueue
    schema_version: str = REVALIDATION_PROGRESS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.index, DependencyIndex)
                or not isinstance(self.queue, RevalidationQueue)
                or self.schema_version != REVALIDATION_PROGRESS_SCHEMA):
            _invalid("BAMF_C09_REVALIDATION_PROGRESS_INVALID")


def _task(node: ArtifactNode, cause: DependencyRef) -> RevalidationTask:
    return RevalidationTask(
        node.artifact_id, node.exigency, node.impact, cause)
