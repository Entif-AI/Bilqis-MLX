"""Draft consumer methods for source-bound output and transformation witnesses.

Results are finite proof observations. They do not discharge a live release's
review, prerequisites, native mapping, morphology or construction-family debt.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..curriculum_contracts import (CapabilityConstructionContract, ConstructionFamily,
    FamilyDisposition, FamilyObligation)
from ..semantics.foundation.catalog import Catalog, SemanticCatalog
from ..semantics.foundation.core import Apply, Expression, Literal, TypedError, expression_digest, literal
from ..semantics.foundation.domains import AnswerContract, AnswerMode, contract_digest, require_sha256
from ..semantics.foundation.laws import LawCandidate
from .cases import verify_constituents
from .expressions import Backend, Proof
from .laws import LawCheck, check_finite_equivalence


@dataclass(frozen=True)
class DomainWitness:
    answer_contract_sha256: str
    expression_sha256: str
    value: Literal
    proofs: tuple[Proof, ...]
    construction_contract_sha256: str
    native_token_index: int | None = None
    source_qualified: bool = field(default=False, init=False)


def verify_native_mapping(answer: AnswerContract, catalog: SemanticCatalog | None) -> None:
    """Match declared answer identities to an actual code-owned catalog release.

    The externally reviewed answer contract owns literal-to-identity meaning;
    this checks the catalog index/identity/type, without inferring semantics
    from an English name or allocating a token.
    """
    if not isinstance(catalog, SemanticCatalog):
        raise TypedError("CONSTRUCTION_NATIVE_CATALOG_REQUIRED")
    if catalog.digest != answer.catalog_sha256:
        raise TypedError("CONSTRUCTION_NATIVE_CATALOG_DRIFT")
    identities = dict(answer.native_identities)
    if set(identities) != set(answer.domain.values):
        raise TypedError("CONSTRUCTION_NATIVE_IDENTITY_BINDINGS_REQUIRED")
    for value, index in answer.native_tokens:
        token = catalog.token(index)
        if (token.identity != identities[value] or token.arity != 0 or
                token.signature != value.type_name):
            raise TypedError("CONSTRUCTION_NATIVE_IDENTITY_DRIFT")


def verify_domain_witness(expression: Apply, *, contract: CapabilityConstructionContract,
                          expected_contract_sha256: str, catalog: Catalog,
                          source: Backend, independent: Backend,
                          semantic_catalog: SemanticCatalog | None = None) -> DomainWitness:
    require_sha256(expected_contract_sha256)
    if not isinstance(contract, CapabilityConstructionContract) or contract_digest(contract) != expected_contract_sha256:
        raise TypedError("CONSTRUCTION_CONTRACT_PIN_MISMATCH")
    answer = contract.answer
    if not isinstance(catalog, Catalog):
        raise TypedError("CONSTRUCTION_OPERATION_CATALOG_REQUIRED")
    if any(not isinstance(getattr(backend, "identity", None), str)
           or not backend.identity.strip() or not callable(getattr(backend, "invoke", None))
           for backend in (source, independent)):
        raise TypedError("CONSTRUCTION_INDEPENDENT_BACKENDS_REQUIRED")
    if not isinstance(expression, Apply) or expression.type_name != answer.domain.type_name:
        raise TypedError("CONSTRUCTION_ANSWER_EXPRESSION_TYPE_MISMATCH")

    leaves, intermediates = {}, {}
    def bound(node: Expression, path=()):
        if isinstance(node, Apply):
            if catalog.get(node.operator.token_index) != node.operator:
                raise TypedError("CONSTRUCTION_OPERATION_CATALOG_DRIFT")
            if path:
                intermediates[path] = node
            for slot, child in enumerate(node.arguments):
                bound(child, (*path, slot))
        else:
            leaves[path] = node

    bound(expression)
    inputs = {binding.path: binding.domain for binding in contract.inputs}
    domains = {binding.path: binding.domain for binding in contract.intermediates}
    if len(inputs) != len(contract.inputs) or set(inputs) != set(leaves):
        raise TypedError("CONSTRUCTION_INPUT_DOMAIN_PATH_MISMATCH")
    if len(domains) != len(contract.intermediates) or set(domains) != set(intermediates):
        raise TypedError("CONSTRUCTION_INTERMEDIATE_DOMAIN_PATH_MISMATCH")
    for path, value in leaves.items():
        if not inputs[path].closed or not inputs[path].accepts(value):
            raise TypedError("CONSTRUCTION_INPUT_DOMAIN_MISMATCH")
    proofs = verify_constituents(expression, source=source, independent=independent)
    # Backends must preserve the existing wire ABI. Python numeric results need
    # a separately reviewed codec adapter before they enter Proof.result.
    if any(type(proof.result) not in (str, bool) for proof in proofs):
        raise TypedError("CONSTRUCTION_BACKEND_RESULT_NOT_CANONICAL_WIRE_VALUE")
    by_expression = {proof.expression_sha256: proof for proof in proofs}
    for path, node in intermediates.items():
        value = literal(by_expression[expression_digest(node)].result, node.type_name,
                        world_contract=node.world_contract)
        if not domains[path].closed or not domains[path].accepts(value):
            raise TypedError("CONSTRUCTION_INTERMEDIATE_DOMAIN_MISMATCH")
    value = literal(proofs[-1].result, expression.type_name,
                    world_contract=expression.world_contract)
    if not answer.domain.closed or not answer.domain.accepts(value):
        raise TypedError("CONSTRUCTION_GOLD_OUTSIDE_OUTPUT_DOMAIN")
    native = None
    if answer.mode is AnswerMode.NATIVE_TOKEN:
        verify_native_mapping(answer, semantic_catalog)
        native = answer.token_for(value)
    return DomainWitness(contract_digest(answer), expression_digest(expression), value, proofs,
                         expected_contract_sha256, native)


@dataclass(frozen=True)
class TransformationWitness:
    obligation_sha256: str
    cohort_sha256: str
    transformation_pairs: tuple[tuple[str, str], ...]
    check: LawCheck
    specimen_sha256: tuple[str, ...]
    qualification_gaps: tuple[str, ...] = ("EXECUTABLE_TRANSFORMATION_ATTESTATION_REQUIRED",)


def verify_transformation_family(
    obligation: FamilyObligation, law: LawCandidate, specimens: tuple[Expression, ...], *,
    expected_obligation_sha256: str, catalog: Catalog, source: Backend,
    independent: Backend,
) -> TransformationWitness:
    """Reuse finite law falsification; keep counterexample and UNKNOWN outcomes."""
    require_sha256(expected_obligation_sha256)
    if (not isinstance(obligation, FamilyObligation) or not isinstance(law, LawCandidate)
            or not isinstance(specimens, tuple) or any(not isinstance(x, (Apply, Literal)) for x in specimens)):
        raise TypedError("CONSTRUCTION_INVALID_TRANSFORMATION_INPUT")
    if contract_digest(obligation) != expected_obligation_sha256:
        raise TypedError("CONSTRUCTION_FAMILY_PIN_MISMATCH")
    if (obligation.disposition is not FamilyDisposition.REQUIRED
            or obligation.family not in (ConstructionFamily.RECONSTRUCTION,
                                         ConstructionFamily.INVERSE)
            or obligation.source is None or obligation.source.locator != law.source):
        raise TypedError("CONSTRUCTION_UNSUPPORTED_OR_UNBOUND_TRANSFORMATION")
    cohort = tuple(expression_digest(expression) for expression in specimens)
    if not isinstance(catalog, Catalog) or catalog.get(law.subject.token_index) != law.subject:
        raise TypedError("CONSTRUCTION_OPERATION_CATALOG_DRIFT")
    def bound(node):
        if isinstance(node, Apply):
            if catalog.get(node.operator.token_index) != node.operator:
                raise TypedError("CONSTRUCTION_OPERATION_CATALOG_DRIFT")
            for child in node.arguments:
                bound(child)
    for expression in specimens:
        if expression.type_name != law.input_type or expression.world_contract != law.world_contract:
            raise TypedError("CONSTRUCTION_TRANSFORMATION_INPUT_SCOPE_MISMATCH")
        bound(expression)
    prepared, applicable = {}, {}
    for expression in specimens:
        first, second = law.precondition(expression), law.precondition(expression)
        if type(first) is not bool or type(second) is not bool or first != second:
            raise TypedError("CONSTRUCTION_NONDETERMINISTIC_PRECONDITION")
        identity = expression_digest(expression)
        applicable[identity] = first
        if first:
            before, after = law.transform(expression), law.transform(expression)
            if not isinstance(before, (Apply, Literal)) or not isinstance(after, (Apply, Literal)):
                raise TypedError("CONSTRUCTION_INVALID_TRANSFORMED_EXPRESSION")
            if expression_digest(before) != expression_digest(after):
                raise TypedError("CONSTRUCTION_NONDETERMINISTIC_TRANSFORMATION")
            if identity in prepared and prepared[identity] != before:
                raise TypedError("CONSTRUCTION_NONDETERMINISTIC_TRANSFORMATION")
            prepared[identity] = before
    pairs = []

    def record(expression):
        transformed = prepared[expression_digest(expression)]
        pairs.append((expression_digest(expression), expression_digest(transformed)))
        return transformed

    check = check_finite_equivalence(
        replace(law, precondition=lambda x: applicable[expression_digest(x)], transform=record),
        specimens, catalog=catalog, source=source,
        independent=independent, scope=contract_digest({
            "obligation": expected_obligation_sha256, "cohort": cohort}))
    return TransformationWitness(expected_obligation_sha256, contract_digest(cohort),
                                 tuple(pairs), check, cohort)
