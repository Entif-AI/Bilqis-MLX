"""Runtime inputs closed over one verified executable factory release."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, FACTORY, SCHOOL
from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.semantics.domains import contract_digest

from dataclasses import dataclass, field
from pathlib import Path

from ..factory.adapters import SourceAdapterRegistry
from ..factory.answers import AnswerModalityRegistry
from ..factory.executable_release import ExecutableFactoryRelease


_SOURCE_BATCH_ISSUER = object()
_DERIVED_ROW_KEYS = frozenset(("grade", "native_output", "auxiliary_labels"))


def _invalid_source_batch(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_TRAINING_ADAPTER.INVALID, reason=reason)


def _source_content(rows) -> str:
    return content_digest(tuple(
        {key: value for key, value in row.items() if key not in _DERIVED_ROW_KEYS}
        for row in rows))


def source_content_digest(rows) -> str:
    """Digest source-owned row content without derived/reporting fields."""
    return _source_content(rows)


def _source_family(execution, *, seed: int, each: int) -> str:
    return contract_digest({
        "schema": "bilqis.mlx.source-draw-family/v1",
        "provider": execution.provider_id,
        "implementation": execution.provider_implementation_sha256,
        "capability": execution.capability_id,
        "seed": seed,
        "each": each,
    })


def _source_episode(family: str, row: dict) -> str:
    return row["id"]


@dataclass(frozen=True, init=False)
class SourceBatchAuthority:
    release_sha256: str
    capability_id: str
    provider_id: str
    provider_implementation_sha256: str
    seed: int
    each: int
    content_sha256: str
    source_family_id: str
    episode_ids: tuple[str, ...]
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid_source_batch("FACTORY_SOURCE_BATCH_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _SOURCE_BATCH_ISSUER
                or not all(isinstance(value, str) and value for value in (
                    self.release_sha256, self.capability_id, self.provider_id,
                    self.provider_implementation_sha256, self.content_sha256,
                    self.source_family_id))
                or type(self.seed) is not int or self.seed < 0
                or type(self.each) is not int or self.each < 1
                or type(self.episode_ids) is not tuple
                or len(self.episode_ids) != self.each
                or any(not isinstance(value, str) or not value
                       for value in self.episode_ids)):
            _invalid_source_batch("FACTORY_SOURCE_BATCH_AUTHORITY_INVALID")


@dataclass(frozen=True)
class SourceExecutionContext:
    release: ExecutableFactoryRelease
    graph: dict
    source_root: Path | None
    source_registry: SourceAdapterRegistry
    answer_registry: AnswerModalityRegistry

    @classmethod
    def from_admitted_release(
            cls, run_dir: Path, receipt: dict, *, graph: dict,
            source_root: Path | None, source_registry: SourceAdapterRegistry,
            answer_registry: AnswerModalityRegistry) -> SourceExecutionContext:
        from .admission import (
            _read_executable_factory_release_artifact as _read_executable_factory_release)

        release = _read_executable_factory_release(run_dir, receipt)
        return cls(release=release, graph=graph, source_root=source_root,
                   source_registry=source_registry, answer_registry=answer_registry)

    def __post_init__(self) -> None:
        if not isinstance(self.release, ExecutableFactoryRelease):
            raise TypeError(FACTORY.EXECUTION.EXPECTED_AN_EXECUTABLEFACTORYRELEASE.legacy_codes[0])
        if not isinstance(self.source_registry, SourceAdapterRegistry):
            raise TypeError(FACTORY.EXECUTION.EXPECTED_A_SOURCEADAPTERREGISTRY.legacy_codes[0])
        if not isinstance(self.answer_registry, AnswerModalityRegistry):
            raise TypeError(FACTORY.EXECUTION.EXPECTED_AN_ANSWERMODALITYREGISTRY.legacy_codes[0])
        self.release.verify()
        self.release.verify_semantic_catalog(self.graph)
        bindings = self.release.source_bindings.by_capability
        for capability in self.release.execution_plan.capabilities:
            binding = bindings[capability.capability_id]
            self.source_registry.require(binding.generator_id, binding.oracle_id)
        self.answer_registry.validate_plan(self.release.execution_plan)

    def require_capabilities(self, capabilities: tuple[str, ...]) -> None:
        """Check a complete host request before any of its providers run."""
        admitted = self.release.execution_plan.capability_map
        if any(capability not in admitted for capability in capabilities):
            raise ErrorBus.legacy_error(FACTORY.EXECUTION.EXECUTABLE_GENERATION_UNKNOWN_CAPABILITY)

    def draw_rows(self, *, seed: int, capability: str | None = None,
                  each: int | None = None) -> list[dict]:
        """Draw only the bound release's admitted capability/provider scope."""
        from ..factory.generation import draw_executable_release_rows

        return draw_executable_release_rows(
            self.source_root, self.graph, self.release, self.source_registry,
            seed=seed, capability=capability, each=each)

    def bind_rows(self, rows, *, seed: int, capability: str,
                  each: int) -> SourceBatchAuthority:
        """Issue process-live authority only for an exact owner-redrawn batch."""
        if (not isinstance(rows, (tuple, list)) or not rows
                or type(seed) is not int or seed < 0
                or not isinstance(capability, str) or not capability
                or type(each) is not int or each < 1):
            _invalid_source_batch("FACTORY_SOURCE_BATCH_BINDING_INVALID")
        expected = self.draw_rows(seed=seed, capability=capability, each=each)
        if _source_content(rows) != _source_content(expected):
            _invalid_source_batch("FACTORY_SOURCE_BATCH_CONTENT_DRIFT")
        execution = self.release.execution_plan.capability_map[capability]
        content = _source_content(expected)
        family = _source_family(execution, seed=seed, each=each)
        episodes = tuple(_source_episode(family, row) for row in expected)
        authority = object.__new__(SourceBatchAuthority)
        for name, value in (
                ("release_sha256", self.release.release_sha256),
                ("capability_id", capability),
                ("provider_id", execution.provider_id),
                ("provider_implementation_sha256",
                 execution.provider_implementation_sha256),
                ("seed", seed), ("each", each), ("content_sha256", content),
                ("source_family_id", family), ("episode_ids", episodes),
                ("_issuance", _SOURCE_BATCH_ISSUER)):
            object.__setattr__(authority, name, value)
        authority.__post_init__()
        return authority


__all__ = (
    "SourceBatchAuthority", "SourceExecutionContext", "source_content_digest",
)
