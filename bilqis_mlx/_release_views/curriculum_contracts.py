"""Unqualified construction planning through the existing curriculum AST.

No live compiler/admission caller imports this opt-in scaffold. Completeness
here concerns declared finite inputs; external source review must establish
that those inputs and family dispositions match the actual semantic scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .curriculum_compiler import CurriculumAST, FiniteTypedInput, TypedExpressionTemplate
from .curriculum_compiler import dependency_coverage_plan
from .semantics.domains import AnswerContract, FiniteDomain, SourceBinding, contract_digest


class ConstructionFamily(str, Enum):
    DIRECT = "DIRECT"
    COMPOSITION = "COMPOSITION"
    DECOMPOSITION = "DECOMPOSITION"
    RECONSTRUCTION = "RECONSTRUCTION"
    CONTRAST = "CONTRAST"
    INVERSE = "INVERSE"
    NEGATIVE = "NEGATIVE"
    INVALID = "INVALID"


class FamilyDisposition(str, Enum):
    REQUIRED = "REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNREVIEWED = "UNREVIEWED"


class ContractPlanStatus(str, Enum):
    UNQUALIFIED_PROPOSAL = "UNQUALIFIED_CONTRACT_PROPOSAL"


@dataclass(frozen=True)
class FamilyObligation:
    family: ConstructionFamily
    disposition: FamilyDisposition
    rationale: str
    source: SourceBinding | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.family, ConstructionFamily)
                or not isinstance(self.disposition, FamilyDisposition)
                or not isinstance(self.rationale, str) or not self.rationale.strip()):
            raise ValueError("CONSTRUCTION_INVALID_FAMILY_OBLIGATION")
        if (self.disposition is not FamilyDisposition.UNREVIEWED
                and not isinstance(self.source, SourceBinding)):
            raise ValueError("CONSTRUCTION_FAMILY_SOURCE_REQUIRED")
        if self.source is not None and not isinstance(self.source, SourceBinding):
            raise ValueError("CONSTRUCTION_FAMILY_SOURCE_INVALID")


@dataclass(frozen=True)
class LeafDomainBinding:
    path: tuple[int, ...]
    domain: FiniteDomain

    def __post_init__(self) -> None:
        if (not isinstance(self.path, tuple) or not self.path
                or any(type(slot) is not int or slot < 0 for slot in self.path)
                or not isinstance(self.domain, FiniteDomain)):
            raise ValueError("CONSTRUCTION_INVALID_LEAF_BINDING")


@dataclass(frozen=True)
class CapabilityConstructionContract:
    capability: str
    inputs: tuple[LeafDomainBinding, ...]
    answer: AnswerContract
    families: tuple[FamilyObligation, ...]
    intermediates: tuple[LeafDomainBinding, ...] = ()

    def __post_init__(self) -> None:
        if (not isinstance(self.capability, str) or not self.capability.strip()
                or not isinstance(self.answer, AnswerContract)
                or not isinstance(self.inputs, tuple) or not self.inputs
                or not isinstance(self.families, tuple)
                or not isinstance(self.intermediates, tuple)
                or any(not isinstance(item, LeafDomainBinding) for item in self.intermediates)
                or any(not isinstance(item, LeafDomainBinding) for item in self.inputs)
                or any(not isinstance(item, FamilyObligation) for item in self.families)):
            raise ValueError("CONSTRUCTION_INVALID_CAPABILITY_CONTRACT")


@dataclass(frozen=True)
class ConstructionContractPlan:
    ast_sha256: str
    contracts_sha256: str
    templates_sha256: str
    finite_counts: tuple[tuple[str, int], ...]
    required_families: tuple[tuple[str, ConstructionFamily], ...]
    coverage_debt: tuple[str, ...]
    status: ContractPlanStatus = ContractPlanStatus.UNQUALIFIED_PROPOSAL
    training_authorized: bool = field(default=False, init=False)


def template_leaves(template: TypedExpressionTemplate, path=()):
    for slot, child in enumerate(template.arguments):
        current = (*path, slot)
        if isinstance(child, TypedExpressionTemplate):
            yield from template_leaves(child, current)
        elif isinstance(child, FiniteTypedInput):
            yield current, child
        else:
            raise ValueError("CONSTRUCTION_UNSUPPORTED_TEMPLATE_ARGUMENT")


def template_intermediates(template: TypedExpressionTemplate, path=()):
    for slot, child in enumerate(template.arguments):
        if isinstance(child, TypedExpressionTemplate):
            current = (*path, slot)
            yield current, child
            yield from template_intermediates(child, current)


def plan_construction_contracts(
    ast: CurriculumAST, *, templates: Mapping[str, TypedExpressionTemplate],
    contracts: Mapping[str, CapabilityConstructionContract], construction_budget: int,
) -> ConstructionContractPlan:
    """Expose debt without changing existing Boolean package qualification."""
    if not isinstance(ast, CurriculumAST):
        raise ValueError("CONSTRUCTION_INVALID_AST")
    dependency_coverage_plan(ast)
    if type(construction_budget) is not int or construction_budget < 1:
        raise ValueError("CONSTRUCTION_INVALID_BUDGET")
    nodes = {node.id: node for node in ast.nodes}
    if (not isinstance(contracts, Mapping) or not isinstance(templates, Mapping)
            or not contracts or set(contracts) != set(templates) or not set(templates) <= nodes.keys()):
        raise ValueError("CONSTRUCTION_TARGET_BINDING_MISMATCH")
    debt, counts, required = [], [], []
    for identity in sorted(contracts):
        contract, template = contracts[identity], templates[identity]
        if (not isinstance(contract, CapabilityConstructionContract)
                or not isinstance(template, TypedExpressionTemplate) or contract.capability != identity):
            raise ValueError("CONSTRUCTION_CAPABILITY_BINDING_MISMATCH")
        leaves = dict(template_leaves(template))
        declared = {binding.path: binding.domain for binding in contract.inputs}
        if len(declared) != len(contract.inputs) or set(declared) != set(leaves):
            raise ValueError("CONSTRUCTION_LEAF_COVERAGE_MISMATCH")
        for path, leaf in leaves.items():
            domain = declared[path]
            if (domain.type_name != leaf.type_name or domain.world_contract != leaf.world_contract
                    or tuple((type(value.value), value.value) for value in domain.values)
                    != tuple((type(value), value) for value in leaf.values)):
                raise ValueError("CONSTRUCTION_INPUT_DOMAIN_MISMATCH")
            if not domain.closed:
                debt.append(f"OPEN_INPUT_DOMAIN:{identity}:{path}")
        intermediate_templates = dict(template_intermediates(template))
        intermediate_domains = {binding.path: binding.domain for binding in contract.intermediates}
        if len(intermediate_domains) != len(contract.intermediates) or set(intermediate_domains) - set(intermediate_templates):
            raise ValueError("CONSTRUCTION_INTERMEDIATE_COVERAGE_MISMATCH")
        for path, child in intermediate_templates.items():
            domain = intermediate_domains.get(path)
            if domain is None:
                debt.append(f"MISSING_INTERMEDIATE_DOMAIN:{identity}:{path}")
            elif domain.type_name != child.operation.signature.output:
                raise ValueError("CONSTRUCTION_INTERMEDIATE_TYPE_MISMATCH")
            elif not domain.closed:
                debt.append(f"OPEN_INTERMEDIATE_DOMAIN:{identity}:{path}")
        if contract.answer.domain.type_name != template.operation.signature.output:
            raise ValueError("CONSTRUCTION_OUTPUT_TYPE_MISMATCH")
        if not contract.answer.domain.closed:
            debt.append(f"OPEN_OUTPUT_DOMAIN:{identity}")
        if tuple(nodes[identity].answers) != (contract.answer.mode.value,):
            debt.append(f"AST_ANSWER_FAMILY_NOT_MIGRATED:{identity}")
        families = {item.family: item for item in contract.families}
        if len(families) != len(contract.families):
            raise ValueError("CONSTRUCTION_DUPLICATE_FAMILY_DISPOSITION")
        for family in ConstructionFamily:
            item = families.get(family)
            if item is None or item.disposition is FamilyDisposition.UNREVIEWED:
                debt.append(f"UNREVIEWED_FAMILY:{identity}:{family.value}")
            elif item.disposition is FamilyDisposition.REQUIRED:
                required.append((identity, family))
                debt.append(f"MISSING_FAMILY_WITNESSES:{identity}:{family.value}")
        count = template.construction_count
        counts.append((identity, count))
        if count > construction_budget:
            debt.append(f"FINITE_DOMAIN_OVER_BUDGET:{identity}:{count}/{construction_budget}")
    return ConstructionContractPlan(ast.digest(), contract_digest(contracts), contract_digest(templates),
                                    tuple(counts), tuple(required), tuple(debt))
