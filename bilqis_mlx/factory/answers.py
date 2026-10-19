"""Typed answer-modality registry and execution-plan head compiler.

Grade identity never selects an output head. Capabilities declare answer families;
one registered modality adapter validates each active value domain and maps labels
to semantic identities already present in the model graph.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .execution import ExecutionPlan


Canonicalize = Callable[[tuple[str, ...]], tuple[str, ...]]
ResolveIdentity = Callable[[str], str]


@dataclass(frozen=True)
class AnswerModality:
    kind: str
    adapter_id: str
    implementation_sha256: str

    def __post_init__(self) -> None:
        if (not isinstance(self.kind, str) or not self.kind or
                not isinstance(self.adapter_id, str) or not self.adapter_id or
                not isinstance(self.implementation_sha256, str) or
                len(self.implementation_sha256) != 64 or
                any(c not in "0123456789abcdef" for c in self.implementation_sha256)):
            raise ValueError("FACTORY_ANSWER_MODALITY_IDENTITY_INVALID")


@dataclass(frozen=True)
class RegisteredAnswerModality:
    descriptor: AnswerModality
    canonicalize: Canonicalize
    resolve_identity: ResolveIdentity

    def __post_init__(self) -> None:
        if not callable(self.canonicalize) or not callable(self.resolve_identity):
            raise ValueError("FACTORY_ANSWER_MODALITY_IMPLEMENTATION_REQUIRED")


class AnswerModalityRegistry:
    def __init__(self, modalities=()):
        self._by_kind: dict[str, RegisteredAnswerModality] = {}
        for modality in modalities:
            self.register(modality)

    def register(self, modality: RegisteredAnswerModality) -> None:
        if not isinstance(modality, RegisteredAnswerModality):
            raise TypeError("FACTORY_INVALID_REGISTERED_ANSWER_MODALITY")
        kind = modality.descriptor.kind
        if kind in self._by_kind:
            raise ValueError("FACTORY_DUPLICATE_ANSWER_MODALITY:" + kind)
        self._by_kind[kind] = modality

    def require(self, kind: str) -> RegisteredAnswerModality:
        item = self._by_kind.get(kind)
        if item is None:
            raise ValueError("FACTORY_ANSWER_MODALITY_MISSING:" + str(kind))
        return item

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(self._by_kind)

    def descriptors_for(self, plan: ExecutionPlan) -> tuple[AnswerModality, ...]:
        kinds = []
        for capability in plan.capabilities:
            for family in capability.answer_families:
                if family.kind not in kinds:
                    kinds.append(family.kind)
        return tuple(self.require(kind).descriptor for kind in kinds)

    def validate_plan(self, plan: ExecutionPlan) -> None:
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("FACTORY_ANSWER_MODALITY_PLAN_REQUIRED")
        _merge_families(plan, self)


def fixed_domain(values: tuple[str, ...]) -> Canonicalize:
    canonical = tuple(values)
    if not canonical or len(set(canonical)) != len(canonical):
        raise ValueError("FACTORY_ANSWER_MODALITY_CANONICAL_DOMAIN_INVALID")

    def validate(active: tuple[str, ...]) -> tuple[str, ...]:
        active = tuple(active)
        if (not active or not set(active) <= set(canonical) or
                active != tuple(value for value in canonical if value in active)):
            raise ValueError("FACTORY_ANSWER_MODALITY_VALUE_DOMAIN_DRIFT")
        return active

    return validate


def merge_prefix_domain(active: tuple[str, ...]) -> tuple[str, ...]:
    """Validate zero-based numeric labels used by an active bounded numeric head."""
    active = tuple(active)
    if (len(active) < 2 or active != tuple(str(i) for i in range(len(active)))):
        raise ValueError("FACTORY_ANSWER_MODALITY_VALUE_DOMAIN_DRIFT")
    return active


def _merge_families(plan: ExecutionPlan, registry: AnswerModalityRegistry):
    by_kind: dict[str, list[tuple[str, ...]]] = {}
    for capability in plan.capabilities:
        for family in capability.answer_families:
            by_kind.setdefault(family.kind, []).append(tuple(family.values))
    merged = {}
    for kind, domains in by_kind.items():
        modality = registry.require(kind)
        # A head must cover every active label for its modality. Preserve first
        # occurrence order, then let the modality enforce its canonical domain.
        union = tuple(dict.fromkeys(value for domain in domains for value in domain))
        merged[kind] = modality.canonicalize(union)
    return merged


def compile_answer_heads(plan: ExecutionPlan, graph: dict,
                         registry: AnswerModalityRegistry) -> dict[str, dict]:
    """Bind plan-declared answer domains to the model's existing semantic ABI."""
    if not isinstance(plan, ExecutionPlan) or not isinstance(registry, AnswerModalityRegistry):
        raise TypeError("FACTORY_ANSWER_HEAD_COMPILATION_INVALID_INPUT")
    names = graph.get("tokens") if isinstance(graph, dict) else None
    if (not isinstance(names, list) or not names or len(set(names)) != len(names) or
            any(not isinstance(name, str) or not name for name in names)):
        raise ValueError("FACTORY_ANSWER_HEAD_GRAPH_INVALID")
    result = {
        "semantic_token": {
            "values": list(names),
            "token_ids": list(range(len(names))),
        }
    }
    for kind, values in _merge_families(plan, registry).items():
        modality = registry.require(kind)
        identities = tuple(modality.resolve_identity(value) for value in values)
        if (len(set(identities)) != len(identities) or
                any(not isinstance(identity, str) or identity not in names
                    for identity in identities)):
            raise ValueError("FACTORY_ANSWER_MODALITY_SEMANTIC_BINDING_MISSING:" + kind)
        result[kind] = {
            "values": list(values),
            "token_ids": [names.index(identity) for identity in identities],
            "modality_id": modality.descriptor.adapter_id,
            "implementation_sha256": modality.descriptor.implementation_sha256,
        }
    return result
