"""Compile explicitly defined candidate semantics through the executable factory.

Source extraction supplies identity and provenance. Semantic definitions and
registered source/oracle implementations supply behavior. Staging verifies their
connection; learner readiness and student-bound admission remain separate steps.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .candidate_frontier import CandidateFrontierRelease
from .curriculum_definition import CurriculumDefinition, SourceBindingSet
from .executable_release import ExecutableFactoryRelease, compile_executable_factory_release
from .jit_curriculum import CandidateBinding, _digest


SCHEMA = "bilqis.mlx.staged-candidate/v1"
_SOURCE_BINDING_MISMATCH = "CANDIDATE_STAGING_SOURCE_BINDING_MISMATCH"
_DIGEST_MISMATCH = "CANDIDATE_STAGING_DIGEST_MISMATCH"
_MANIFEST_INVALID = "CANDIDATE_STAGING_MANIFEST_INVALID"


def _target(frontier, candidate_id):
    frontier.verify()
    candidate = next((item for item in frontier.candidates
                      if item.candidate_id == candidate_id), None)
    if (candidate is None or not candidate.proposed_capability_id or
            not candidate.target_sense_id or not candidate.source_evidence_ids):
        raise ValueError("CANDIDATE_STAGING_EXACT_TARGET_REQUIRED")
    sense = next(item for item in frontier.senses
                 if item.sense_id == candidate.target_sense_id)
    return candidate, sense


def candidate_source_anchor(frontier: CandidateFrontierRelease, candidate_id: str) -> str:
    """Content-address the source sense without assigning a token or meaning."""
    _, sense = _target(frontier, candidate_id)
    return f"ithkuil:sense/{sense.sense_id}@sha256:{sense.source_text_sha256}"


def _verify_delta(frontier, current, candidate_id, successor):
    candidate, _ = _target(frontier, candidate_id)
    successor.verify_successor_of(current)
    target = candidate.proposed_capability_id
    delta = successor.transition
    if (delta is None or delta.added_capabilities != (target,) or
            delta.removed_capabilities or delta.changed_capabilities or
            delta.removed_grades):
        raise ValueError("CANDIDATE_STAGING_DELTA_SCOPE_MISMATCH")
    _preserve_existing_authority(current, successor.curriculum, successor.source_bindings)
    binding = successor.source_bindings.by_capability.get(target)
    if binding is None or binding.source_anchor != candidate_source_anchor(frontier, candidate_id):
        raise ValueError(_SOURCE_BINDING_MISMATCH)
    execution = successor.execution_plan.capability_map[target]
    explicit = set(execution.prerequisites) | set(execution.composed_of)
    if not {edge.capability_id for edge in candidate.prerequisites} <= explicit:
        raise ValueError("CANDIDATE_STAGING_PREREQUISITE_ACCOUNTING_REQUIRED")


def _preserve_existing_authority(current, curriculum, source_bindings):
    for capability_id, definition in current.curriculum.capability_map.items():
        if (curriculum.capability_map.get(capability_id) != definition or
                source_bindings.by_capability.get(capability_id) !=
                current.source_bindings.by_capability[capability_id]):
            raise ValueError("CANDIDATE_STAGING_EXISTING_AUTHORITY_CHANGED")


@dataclass(frozen=True)
class StagedCandidate:
    frontier_sha256: str
    candidate_id: str
    target_capability_id: str
    source_sense_id: str
    source_anchor: str
    successor: ExecutableFactoryRelease
    staged_sha256: str

    @property
    def binding(self) -> CandidateBinding:
        return CandidateBinding(self.candidate_id, self.target_capability_id,
                                self.source_sense_id, self.source_anchor, self.successor)

    def manifest(self) -> dict:
        return dict(schema=SCHEMA, frontier_sha256=self.frontier_sha256,
                    candidate_id=self.candidate_id, target_capability_id=self.target_capability_id,
                    source_sense_id=self.source_sense_id, source_anchor=self.source_anchor,
                    successor_manifest=self.successor.manifest(),
                    successor_sha256=self.successor.release_sha256)

    def expected_digest(self) -> str:
        return _digest(self.manifest())

    def verify(self, frontier, current) -> None:
        if self.staged_sha256 != self.expected_digest():
            raise ValueError(_DIGEST_MISMATCH)
        frontier.verify()
        current.verify()
        if self.frontier_sha256 != frontier.release_sha256:
            raise ValueError("CANDIDATE_STAGING_FRONTIER_MISMATCH")
        candidate, sense = _target(frontier, self.candidate_id)
        if (self.target_capability_id != candidate.proposed_capability_id or
                self.source_sense_id != sense.sense_id or
                self.source_anchor != candidate_source_anchor(frontier, self.candidate_id)):
            raise ValueError(_SOURCE_BINDING_MISMATCH)
        _verify_delta(frontier, current, self.candidate_id, self.successor)

    @classmethod
    def from_manifest(cls, payload: dict, staged_sha256: str):
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            raise ValueError(_MANIFEST_INVALID)
        if _digest(payload) != staged_sha256:
            raise ValueError(_DIGEST_MISMATCH)
        try:
            return cls(payload["frontier_sha256"], payload["candidate_id"],
                       payload["target_capability_id"], payload["source_sense_id"],
                       payload["source_anchor"], ExecutableFactoryRelease.from_manifest(
                           payload["successor_manifest"], payload["successor_sha256"]),
                       staged_sha256)
        except (KeyError, TypeError) as exc:
            raise ValueError(_MANIFEST_INVALID) from exc


def compile_candidate_successor(
    frontier: CandidateFrontierRelease, current: ExecutableFactoryRelease,
    candidate_id: str, *, curriculum: CurriculumDefinition,
    source_bindings: SourceBindingSet, profile, source_registry, answer_registry,
    source_root, graph: dict, verification_seed: int, legacy_course=None,
) -> StagedCandidate:
    """Stage one source-verified delta without changing learner or school state.

    The curriculum can declare a larger canonical horizon. Its profile must add
    exactly this target to the executable inventory and preserve existing work.
    Current-checkpoint prerequisite mastery is checked by the JIT proposer.
    """
    if (not isinstance(frontier, CandidateFrontierRelease) or
            not isinstance(current, ExecutableFactoryRelease) or
            not isinstance(curriculum, CurriculumDefinition) or
            not isinstance(source_bindings, SourceBindingSet)):
        raise TypeError("CANDIDATE_STAGING_INPUT_INVALID")
    candidate, sense = _target(frontier, candidate_id)
    current.verify()
    _preserve_existing_authority(current, curriculum, source_bindings)
    anchor = candidate_source_anchor(frontier, candidate_id)
    binding = source_bindings.by_capability.get(candidate.proposed_capability_id)
    if binding is None or binding.source_anchor != anchor:
        raise ValueError(_SOURCE_BINDING_MISMATCH)
    successor = compile_executable_factory_release(
        curriculum, source_bindings, profile, source_registry, answer_registry,
        source_root=source_root, graph=graph, verification_seed=verification_seed,
        legacy_course=legacy_course, predecessor=current)
    provisional = StagedCandidate(frontier.release_sha256, candidate_id,
                                  candidate.proposed_capability_id, sense.sense_id,
                                  anchor, successor, "0" * 64)
    staged = replace(provisional, staged_sha256=provisional.expected_digest())
    staged.verify(frontier, current)
    return staged
