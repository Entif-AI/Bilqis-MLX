"""Draft consumer methods for source-bound output and transformation witnesses.

Results are finite proof observations. They do not discharge a live release's
review, prerequisites, native mapping, morphology or construction-family debt.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from ..curriculum_contracts import ConstructionFamily, FamilyDisposition, FamilyObligation
from ..semantics.catalog import Catalog
from ..semantics.core import Apply, Expression, Literal, TypedError, expression_digest, literal
from ..semantics.domains import AnswerContract, contract_digest, require_sha256
from ..semantics.laws import LawCandidate
from .cases import verify_constituents
from .expressions import Backend, Proof
from .laws import LawCheck, check_finite_equivalence


@dataclass(frozen=True)
class DomainWitness:
    answer_contract_sha256: str
    expression_sha256: str
    value: Literal
    proofs: tuple[Proof, ...]


def verify_domain_witness(expression: Apply, *, answer: AnswerContract,
                          expected_answer_sha256: str, catalog: Catalog,
                          source: Backend, independent: Backend) -> DomainWitness:
    require_sha256(expected_answer_sha256)
    if contract_digest(answer) != expected_answer_sha256:
        raise TypedError("CONSTRUCTION_ANSWER_CONTRACT_PIN_MISMATCH")
    if not isinstance(expression, Apply) or expression.type_name != answer.domain.type_name:
        raise TypedError("CONSTRUCTION_ANSWER_EXPRESSION_TYPE_MISMATCH")

    def bound(node: Expression):
        if isinstance(node, Apply):
            if catalog.get(node.operator.token_index) != node.operator:
                raise TypedError("CONSTRUCTION_OPERATION_CATALOG_DRIFT")
            for child in node.arguments:
                bound(child)

    bound(expression)
    proofs = verify_constituents(expression, source=source, independent=independent)
    # Backends must preserve the existing wire ABI. Python numeric results need
    # a separately reviewed codec adapter before they enter Proof.result.
    if any(type(proof.result) not in (str, bool) for proof in proofs):
        raise TypedError("CONSTRUCTION_BACKEND_RESULT_NOT_CANONICAL_WIRE_VALUE")
    value = literal(proofs[-1].result, expression.type_name,
                    world_contract=expression.world_contract)
    if not answer.domain.accepts(value):
        raise TypedError("CONSTRUCTION_GOLD_OUTSIDE_OUTPUT_DOMAIN")
    return DomainWitness(expected_answer_sha256, expression_digest(expression), value, proofs)


@dataclass(frozen=True)
class TransformationWitness:
    obligation_sha256: str
    cohort_sha256: str
    transformation_pairs: tuple[tuple[str, str], ...]
    check: LawCheck


def verify_transformation_family(
    obligation: FamilyObligation, law: LawCandidate, specimens: tuple[Expression, ...], *,
    expected_obligation_sha256: str, catalog: Catalog, source: Backend,
    independent: Backend,
) -> TransformationWitness:
    """Reuse finite law falsification; keep counterexample and UNKNOWN outcomes."""
    require_sha256(expected_obligation_sha256)
    if contract_digest(obligation) != expected_obligation_sha256:
        raise TypedError("CONSTRUCTION_FAMILY_PIN_MISMATCH")
    if (obligation.disposition is not FamilyDisposition.REQUIRED
            or obligation.family not in (ConstructionFamily.RECONSTRUCTION,
                                         ConstructionFamily.INVERSE)
            or obligation.source is None or obligation.source.locator != law.source):
        raise TypedError("CONSTRUCTION_UNSUPPORTED_OR_UNBOUND_TRANSFORMATION")
    cohort = tuple(expression_digest(expression) for expression in specimens)
    pairs = []

    def record(expression):
        transformed = law.transform(expression)
        if not isinstance(transformed, (Apply, Literal)):
            raise TypedError("CONSTRUCTION_INVALID_TRANSFORMED_EXPRESSION")
        pairs.append((expression_digest(expression), expression_digest(transformed)))
        return transformed

    check = check_finite_equivalence(
        replace(law, transform=record), specimens, catalog=catalog, source=source,
        independent=independent, scope=contract_digest({
            "obligation": expected_obligation_sha256, "cohort": cohort}))
    return TransformationWitness(expected_obligation_sha256, contract_digest(cohort),
                                 tuple(pairs), check)
