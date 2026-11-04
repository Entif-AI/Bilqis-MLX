"""Immutable executable Factory release artifact."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from ..answers import AnswerModality
from ..curriculum_definition import CurriculumDefinition, SourceBindingSet
from ..execution import CurriculumDelta, CurriculumProfile, ExecutionPlan, SemanticGeometryChange
from ..model import SourceAdapter
from .common import SCHEMA, _ReleaseError, _digest, _require, _require_sha256, _tuples
from .decode import (_decode_curriculum, _decode_plan, _decode_profile,
                     _decode_source_bindings, _decode_verification)
from .records import AnswerHeadBinding, ExecutableVerificationReceipt
from .verify import (_verify_release_answers, _verify_release_assessments,
                     _verify_release_evidence, _verify_release_lineage,
                     _verify_release_providers, _verify_release_structure)

@dataclass(frozen=True)
class ExecutableFactoryRelease:
    """Version-2 FactoryRelease; the complete executable authority artifact."""

    schema: str
    curriculum: CurriculumDefinition
    source_bindings: SourceBindingSet
    profile: CurriculumProfile
    execution_plan: ExecutionPlan
    semantic_catalog: tuple[str, ...]
    semantic_catalog_sha256: str
    source_adapters: tuple[SourceAdapter, ...]
    answer_modalities: tuple[AnswerModality, ...]
    answer_heads: tuple[AnswerHeadBinding, ...]
    verification: ExecutableVerificationReceipt
    predecessor_release_sha256: str | None
    transition: CurriculumDelta | None
    release_sha256: str
    semantic_graph_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.semantic_graph_sha256 is not None:
            _require_sha256(self.semantic_graph_sha256, _ReleaseError.SEMANTIC_GRAPH_INVALID)
        if self.schema != SCHEMA:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_SCHEMA_INVALID")
        if self.predecessor_release_sha256 is not None:
            _require_sha256(
                self.predecessor_release_sha256,
                "FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_INVALID")
        _require(
            bool(self.semantic_catalog) and
            len(set(self.semantic_catalog)) == len(self.semantic_catalog) and
            all(isinstance(item, str) and item for item in self.semantic_catalog),
            _ReleaseError.CATALOG_INVALID,
        )
        _require_sha256(
            self.semantic_catalog_sha256,
            _ReleaseError.CATALOG_INVALID)
        _require_sha256(
            self.release_sha256, "FACTORY_EXECUTABLE_RELEASE_DIGEST_INVALID")

    def manifest(self) -> dict:
        payload = {
            "schema": self.schema,
            "curriculum": asdict(self.curriculum),
            "source_bindings": asdict(self.source_bindings),
            "profile": asdict(self.profile),
            "execution_plan": asdict(self.execution_plan),
            "semantic_catalog": self.semantic_catalog,
            "semantic_catalog_sha256": self.semantic_catalog_sha256,
            "source_adapters": [asdict(item) for item in self.source_adapters],
            "answer_modalities": [asdict(item) for item in self.answer_modalities],
            "answer_heads": [asdict(item) for item in self.answer_heads],
            "verification": asdict(self.verification),
            "predecessor_release_sha256": self.predecessor_release_sha256,
            "transition": (
                None if self.transition is None else asdict(self.transition)),
        }

        if self.semantic_graph_sha256 is not None:
            payload["semantic_graph_sha256"] = self.semantic_graph_sha256
        return payload

    def expected_digest(self) -> str:
        return _digest(self.manifest())

    def verify(self) -> None:
        answer_kinds = _verify_release_structure(self)
        _verify_release_providers(self)
        _verify_release_answers(self, answer_kinds)
        _verify_release_evidence(self)
        _verify_release_assessments(self)
        _verify_release_lineage(self)

    def verify_semantic_catalog(self, graph: dict) -> None:
        """Bind the offline release artifact to the exact loaded semantic ABI."""
        names = graph.get("tokens") if isinstance(graph, dict) else None
        _require(
            isinstance(names, list) and bool(names) and
            len(set(names)) == len(names) and
            all(isinstance(name, str) and name for name in names),
            _ReleaseError.CATALOG_INVALID,
        )
        _require(
            tuple(names) == self.semantic_catalog and
            _digest(tuple(names)) == self.semantic_catalog_sha256,
            _ReleaseError.CATALOG_DRIFT,
        )
        if self.semantic_graph_sha256 is not None:
            _require(_digest(graph) == self.semantic_graph_sha256,
                     _ReleaseError.SEMANTIC_GRAPH_DRIFT)
        for head in self.answer_heads:
            if any(
                    token_id >= len(names) or
                    names[token_id] != identity
                    for identity, token_id in zip(
                        head.semantic_identities, head.token_ids)):
                raise ValueError(
                    "FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_CATALOG_DRIFT")

    def verify_successor_of(self, predecessor: "ExecutableFactoryRelease") -> None:
        """Verify persisted lineage against the actual predecessor artifact."""
        if not isinstance(predecessor, ExecutableFactoryRelease):
            raise TypeError("FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_REQUIRED")
        predecessor.verify()
        self.verify()
        if (self.predecessor_release_sha256 != predecessor.release_sha256 or
                self.transition is None or
                self.transition.previous_plan_sha256 !=
                predecessor.execution_plan.digest() or
                self.transition.previous_curriculum_sha256 !=
                predecessor.execution_plan.curriculum_sha256 or
                self.transition.previous_source_binding_sha256 !=
                predecessor.execution_plan.source_binding_sha256):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_DRIFT")
        previous = predecessor.semantic_catalog
        current = self.semantic_catalog
        if current == previous:
            expected = SemanticGeometryChange.UNCHANGED.value
        elif current[:len(previous)] == previous:
            expected = SemanticGeometryChange.APPEND_ONLY_EXPANSION.value
        else:
            expected = SemanticGeometryChange.INCOMPATIBLE.value
        if (expected == SemanticGeometryChange.INCOMPATIBLE.value or
                self.transition.semantic_geometry != expected):
            raise ValueError(_ReleaseError.LINEAGE_DRIFT)

    @classmethod
    def from_manifest(
            cls, payload: dict, release_sha256: str) -> "ExecutableFactoryRelease":
        """Decode v2 data without importing provider implementations."""
        try:
            curriculum = _decode_curriculum(payload["curriculum"])
            bindings = _decode_source_bindings(payload["source_bindings"])
            profile = _decode_profile(payload["profile"])
            plan = _decode_plan(payload["execution_plan"])
            verification = _decode_verification(payload["verification"])
            transition = (
                None if payload["transition"] is None
                else CurriculumDelta(**_tuples(payload["transition"])))
            release = cls(
                schema=payload["schema"],
                curriculum=curriculum,
                source_bindings=bindings,
                profile=profile,
                execution_plan=plan,
                semantic_catalog=_tuples(payload["semantic_catalog"]),
                semantic_catalog_sha256=payload["semantic_catalog_sha256"],
                source_adapters=tuple(
                    SourceAdapter(**_tuples(item))
                    for item in payload["source_adapters"]),
                answer_modalities=tuple(
                    AnswerModality(**item) for item in payload["answer_modalities"]),
                answer_heads=tuple(
                    AnswerHeadBinding(**_tuples(item))
                    for item in payload["answer_heads"]),
                verification=verification,
                predecessor_release_sha256=payload["predecessor_release_sha256"],
                transition=transition,
                release_sha256=release_sha256,
                semantic_graph_sha256=payload.get("semantic_graph_sha256"),
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_MANIFEST_INVALID") from exc
        if _digest(payload) != release_sha256:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_MANIFEST_CONTENT_DRIFT")
        release.verify()
        return release
