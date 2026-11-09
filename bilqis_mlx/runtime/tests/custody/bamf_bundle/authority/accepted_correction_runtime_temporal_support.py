"""Source-owned temporal fixture for the accepted C09 runtime."""
from dataclasses import dataclass

from bilqis_mlx.factory.skos_curriculum.source_context import (
    SourceLessonContexts, project_source_lesson_contexts,
    source_lesson_expiry_task,
)
from bilqis_mlx.factory.skos_curriculum.source_context_policy import (
    issue_source_context_transition_authority,
)
from bilqis_mlx.factory.tests.skos.test_source_context import (
    RELEASE, SELECTION, _context,
)
from bilqis_mlx.runtime.atlas_artifact_owner import PackedFrameArtifactOwner
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, SourceFrontier,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import (
    CompiledFrameBatch, CompiledFrameRows, CompiledPosition, PositionKind,
    SourceAtom, _prefix_digest, pack_frame,
)


@dataclass(frozen=True)
class SourceOwnedTemporalCase:
    contexts: SourceLessonContexts
    task: object
    frontier: SourceFrontier
    policy: object
    previous: ApprovedContextProjection
    expiry_task: object
    row: CompiledFrameBatch
    rows: CompiledFrameRows

    @property
    def frames(self):
        return (
            self.contexts.positive.envelope,
            self.contexts.contrast.envelope,
        )

    def owner(self):
        return PackedFrameArtifactOwner(self.rows)


def source_owned_temporal_case() -> SourceOwnedTemporalCase:
    authority = issue_source_context_transition_authority(SELECTION)
    task, policy = authority.task, authority.policy
    positive = _context(
        "fixture:positive", "NI-WEB-CH01:1.0", task, policy,
        authority=authority)
    contrast = _context(
        "fixture:contrast", "NI-WEB-CH01:1.1", task, policy,
        authority=authority)
    grants = tuple(sorted(
        (*positive.grants, *contrast.grants),
        key=lambda item: item.source_handle))
    contexts = SourceLessonContexts(
        RELEASE, positive, contrast, grants, authority)
    frontier = SourceFrontier(
        authority.frontier.rights_epoch,
        authority.frontier.correction_generation,
        grants,
    )
    previous = project_source_lesson_contexts(
        contexts, task, frontier, policy)
    if not isinstance(previous, ApprovedContextProjection):
        raise AssertionError("source-owned context was not approved")
    expiry_task = source_lesson_expiry_task(
        contexts, task, frontier, policy)

    frame = positive.envelope.frame
    schema_map = SchemaTagMap.from_schemas(RELEASE, ())
    packed = pack_frame(frame, schema=None, schema_map=schema_map)
    atom = SourceAtom(0, "fixture", "source:fixture-atom")
    positions = (
        CompiledPosition(0, PositionKind.ATOM, atom=atom),
        CompiledPosition(
            0, PositionKind.CLOSURE, packed=packed,
            frame_handle=positive.envelope.frame_handle),
    )
    version = (
        policy.policy_id, policy.policy_epoch, policy.rights_epoch,
        frontier.correction_generation,
    )
    row = CompiledFrameBatch(
        frame.source_instance_id, RELEASE, 1, positions, schema_map,
        previous.digest, task.scope, version,
        _prefix_digest(
            frame.source_instance_id, RELEASE, 1, schema_map,
            previous.digest, positions, task.scope, version),
    )
    rows = CompiledFrameRows((row,), (positions,), ((True, True),))
    return SourceOwnedTemporalCase(
        contexts, task, frontier, policy, previous, expiry_task, row, rows)
