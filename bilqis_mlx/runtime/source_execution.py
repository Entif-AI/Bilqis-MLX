"""Runtime inputs closed over one verified executable factory release."""
from __future__ import annotations

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

    def __post_init__(self) -> None:
        if not isinstance(self.release, ExecutableFactoryRelease):
            raise TypeError("Expected an ExecutableFactoryRelease")
        if not isinstance(self.source_registry, SourceAdapterRegistry):
            raise TypeError("Expected a SourceAdapterRegistry")
        if not isinstance(self.answer_registry, AnswerModalityRegistry):
            raise TypeError("Expected an AnswerModalityRegistry")
        self.release.verify()
        self.release.verify_semantic_catalog(self.graph)
        bindings = self.release.source_bindings.by_capability
        for capability in self.release.execution_plan.capabilities:
            binding = bindings[capability.capability_id]
            self.source_registry.require(binding.generator_id, binding.oracle_id)
        self.answer_registry.validate_plan(self.release.execution_plan)
