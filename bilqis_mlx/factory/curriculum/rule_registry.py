"""Grade-neutral rule profiles for source-qualified Factory families."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.semantics.cognitive_operators.registry import (
    OperatorRegistry, operator_grant_digest,
)
from bilqis_mlx.semantics.foundation.core import Signature

from .capability_identity_contracts import CapabilityIdentityInput


BOOLEAN_COVERAGE = ("truth-table", "polarity", "legal-connective-pattern")
NUMERIC_COVERAGE = ("number", "successor", "arithmetic", "range", "overflow")
WORLD_COVERAGE = ("actor", "time", "state", "causal-relation")
_BOOLEAN = ("BOOL_AND", "BOOL_IFF", "BOOL_IMPLIES", "BOOL_OR", "BOOL_XOR")
_NUMERIC = ("ADD", "DIV", "MOD", "MUL", "SUB")
_WORLD = ("BEFORE", "IS_OCCURRED", "PARENT_OF", "ROLE_LOOKUP")


@dataclass(frozen=True)
class SemanticRuleProfile:
    identity: CapabilityIdentityInput
    coverage: tuple[str, ...]
    operator_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (type(self.identity) is not CapabilityIdentityInput
                or not self.coverage or not self.operator_ids
                or self.operator_ids != tuple(sorted(set(self.operator_ids)))):
            raise ValueError("FACTORY_SEMANTIC_RULE_PROFILE_INVALID")


class SemanticRuleRegistry:
    def __init__(self, version: str, profiles: tuple[SemanticRuleProfile, ...]):
        if not isinstance(version, str) or not version:
            raise ValueError("FACTORY_SEMANTIC_RULE_REGISTRY_INVALID")
        self.version = version
        self.profiles = profiles
        keys = tuple(item.identity.canonical_payload() for item in profiles)
        if (not profiles or any(type(item) is not SemanticRuleProfile for item in profiles)
                or len(keys) != len(set(keys))):
            raise ValueError("FACTORY_SEMANTIC_RULE_DUPLICATE")

    def require(self, identity: CapabilityIdentityInput) -> SemanticRuleProfile:
        if type(identity) is not CapabilityIdentityInput:
            raise TypeError("FACTORY_SEMANTIC_RULE_IDENTITY_REQUIRED")
        matches = tuple(item for item in self.profiles
                        if item.identity.canonical_payload() == identity.canonical_payload())
        if len(matches) != 1:
            raise ValueError("FACTORY_SEMANTIC_RULE_MISSING")
        return matches[0]


def _profile(registry: OperatorRegistry, semantic_id: str, family: str, operator_id: str, signature: Signature,
             answers: tuple[str, ...], coverage: tuple[str, ...],
             operator_ids: tuple[str, ...]) -> SemanticRuleProfile:
    if type(registry) is not OperatorRegistry:
        raise TypeError("FACTORY_SEMANTIC_RULE_OPERATOR_REGISTRY_REQUIRED")
    for covered_operator_id in operator_ids:
        registry.resolve(covered_operator_id)
    return SemanticRuleProfile(CapabilityIdentityInput(
        semantic_id, family, operator_id, signature, answers), coverage, operator_ids)


def default_semantic_rule_registry(semantic_release: str) -> SemanticRuleRegistry:
    from bilqis_mlx.semantics.cognitive_operators.registry import default_registry
    operators = default_registry(semantic_release)
    return SemanticRuleRegistry("bilqis.factory.semantic-rule-registry/v1", (
        _profile(operators, "legacy:cogal.operator.AND", "boolean_composition", "BOOL_AND", Signature(("Boolean", "Boolean"), "Boolean"),
                 ("binary",), BOOLEAN_COVERAGE, _BOOLEAN),
        _profile(operators, "bilqis.numeric/v1:school.op.ADD", "numeric_composition", "ADD", Signature(("Number", "Number"), "Number"),
                 ("integer",), NUMERIC_COVERAGE, _NUMERIC),
    ))


def world_rule_profile(operators: OperatorRegistry) -> SemanticRuleProfile:
    """Fail closed: operator declarations are not world-source admission evidence."""
    if type(operators) is not OperatorRegistry:
        raise TypeError("FACTORY_SEMANTIC_RULE_OPERATOR_REGISTRY_REQUIRED")
    raise ValueError("FACTORY_WORLD_RULE_SOURCE_AUTHORITY_UNAVAILABLE")
