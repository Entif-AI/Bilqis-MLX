"""Shared fixtures for task-scoped formal lesson tests."""
from __future__ import annotations
import hashlib

from bilqis_mlx.factory.formal_constructive import _resolve_from_bindings
from bilqis_mlx.semantics.atlas_projection import AbiEntry, FormalDomainBinding
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorBinding, SourceKind, SourceOperand, TypedValue, default_registry,
    numeric_domain_digest, operator_grant_digest, source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.core import literal
from bilqis_mlx.semantics.domains import FiniteDomain, SourceBinding, ValueCodec
from bilqis_mlx.semantics.laws import SourceLocator
from bilqis_mlx.semantics.foundation import numeric as released_numeric



RELEASE = "a" * 64
BUNDLE = "b" * 64
SOURCE = "c" * 64
PRINCIPAL = "synthetic:person"
TENANT = "synthetic:tenant"
PURPOSE = "TRAINING"
JURISDICTION = "synthetic:region"
SCOPE = "synthetic:task"
FORMAL = (
    ("legacy:cogal.operator.NOT", "boolean", "BOOL_NOT"),
    ("legacy:cogal.operator.AND", "boolean", "BOOL_AND"),
    ("bilqis.numeric/v1:school.op.COUNT", "numeric", "COUNT"),
    ("bilqis.numeric/v1:school.op.SUCC", "numeric", "SUCC"),
)


def _grant(
    handle: str, evidence: str, *, release: str = RELEASE,
    revoked: bool = False,
) -> SourceGrant:
    return SourceGrant(
        handle, PRINCIPAL, TENANT, PUBLIC_FORMAL, release, evidence,
        (PURPOSE,), (JURISDICTION,), (SCOPE,),
        rights_epoch=1, correction_generation=1, observed_at=2,
        effective_from=0, revoked=revoked)


def _source():
    entries = tuple(
        AbiEntry(index, 0, index, semantic_id, semantic_id,
                 "PRIOR_ACCEPTED_NATIVE_REGISTRY", True, True, "SOURCE_ADMITTED")
        for index, (semantic_id, _, _) in enumerate(FORMAL))
    bindings = (
        FormalDomainBinding(
            "boolean", "synthetic:boolean-source", "d" * 64,
            tuple(item[0] for item in FORMAL if item[1] == "boolean"),
            ("B.NOT", "B.AND")),
        FormalDomainBinding(
            "numeric", "bilqis_mlx/semantics/numeric_v1.json",
            hashlib.sha256(
                released_numeric.CONTRACT_PATH.read_bytes()).hexdigest(),
            tuple(item[0] for item in FORMAL if item[1] == "numeric"),
            ("C.COUNT", "C.SUCCESSOR")))
    return _resolve_from_bindings(
        bindings, entries, default_registry(RELEASE),
        semantic_release=RELEASE, atlas_bundle_id=BUNDLE)


def _case(
    operator_id: str, *values: tuple[str, object],
    release: str = RELEASE,
):
    registry = default_registry(release)
    task = TaskScope(
        PRINCIPAL, TENANT, PURPOSE, release, JURISDICTION, SCOPE,
        observed_frontier=3, effective_time=5, causal_prefix_end=20)
    policy = ContextPolicy(
        "synthetic:policy", 1, 1,
        (PURPOSE,), (PUBLIC_FORMAL,), (JURISDICTION,), (SCOPE,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL, PUBLIC_FORMAL),))
    spec = registry.resolve(operator_id)
    grants = [_grant(
        "source:operator:" + operator_id, operator_grant_digest(spec),
        release=release)]
    operands = []
    typed = []
    for index, (type_name, value) in enumerate(values):
        handle = "source:literal:" + str(index)
        item = TypedValue(type_name, value, release, source_handle=handle)
        operand = SourceOperand(
            item, SourceKind.TASK_VISIBLE, "synthetic:source:" + str(index),
            visible_at_prefix=8)
        operands.append(operand)
        typed.append(item)
        grants.append(_grant(
            handle, source_operand_digest(operand), release=release))
    domain = None
    domain_handle = None
    if operator_id in ("COUNT", "SUCC"):
        domain = FiniteDomain(
            "synthetic:number", "v1", "Number",
            tuple(literal(str(index), "Number") for index in range(11)),
            SourceBinding(SourceLocator("synthetic", "v1", "numbers"), "f" * 64),
            codec=ValueCodec.DECIMAL_INTEGER_TEXT, closed=True)
        domain_handle = "source:numbers"
        grants.append(_grant(
            domain_handle, numeric_domain_digest(domain, release),
            release=release))
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda grant: grant.source_handle)))
    binding = OperatorBinding(
        task, frontier, policy, registry, tuple(operands),
        numeric_domain=domain, numeric_source_handle=domain_handle)
    return binding, tuple(typed)


def _selection():
    return AtlasArtifactSelection("synthetic", BUNDLE, RELEASE, SOURCE)
