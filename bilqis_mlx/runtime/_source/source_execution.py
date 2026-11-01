"""Runtime inputs closed over one verified executable factory release."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, FACTORY

from dataclasses import dataclass
from pathlib import Path

from ..factory.adapters import SourceAdapterRegistry
from ..factory.answers import AnswerModalityRegistry
from ..factory.executable_release import ExecutableFactoryRelease


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
