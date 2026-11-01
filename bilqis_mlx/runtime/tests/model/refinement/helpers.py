"""B06.2 complete A05 prefix plus A13 source-gated prediction-local policy."""
from __future__ import annotations

from dataclasses import dataclass, replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.refinement_policy import (
    RefinementSelection, SourceSalience, prefix_inventory_evidence_digest,
    prefix_inventory_handle, salience_evidence_digest,
    select_prediction_refinements,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextHold, ContextMember,
    ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
    frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import (
    FrameCompilerConfig, SourceAtom, StreamingAST, atom_evidence_digest,
    compile_prefix,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, FrameTree, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)


RELEASE = "a" * 64
PRINCIPAL = "synthetic:student"
TENANT = "synthetic:tenant"
REGION = "synthetic:region"
SCOPE = "synthetic:public"
SOURCE_ID = "synthetic:stream"


@dataclass(frozen=True)
class SourceCase:
    frames: tuple[ContextEligibility, ...]
    task: TaskScope
    frontier: SourceFrontier
    policy: ContextPolicy
    ast: StreamingAST
    config: FrameCompilerConfig

    def select(self, *, frames=None, task=None, frontier=None, **changes):
        actual_frontier = self.frontier if frontier is None else frontier
        arguments = dict(
            frames=self.frames if frames is None else frames,
            source_ast=self.ast,
            compiler_config=replace(self.config, frontier=actual_frontier),
            task_scope=self.task if task is None else task,
            source_frontier=actual_frontier,
            policy=self.policy,
            input_generation="generation:1",
            query_id="query:1",
            requested_roles=("target",),
            run_seed="run:1",
            visit_id="visit:1",
            training=False,
            explicit_member_question=True,
            unresolved_nested_query=False,
        )
        arguments.update(changes)
        return select_prediction_refinements(**arguments)


def _case(count=9, *, target_indices=(4, 8)):
    frames = []
    grants = []
    schemas = {}
    for index in range(count):
        role = "target" if index in target_indices else "other"
        schema = FrameSchema(
            "synthetic:" + role, 1, "source:synthetic",
            (RoleSpec(role, ("Entity",), 1, 1),), "ORDERED", "synthetic")
        schemas[schema.identity] = schema
        frame = make_frame_instance(
            schema, source_instance_id=SOURCE_ID,
            structural_path=(index,), source_span=SourceSpan(index, index + 1),
            parent_occurrence_id=None,
            bindings=(RoleOccurrence(role, 0, concept=ConceptRef(
                f"formal:entity.{index}", RELEASE, index, ("Entity",),
                f"source:concept:{index}")),),
            causal_prefix_end=index + 1,
        )
        member = ContextMember(role, 0, f"source:member:{index}", index + 1)
        frame_handle = f"frame:{index}"
        source_handle = f"source:frame:{index}"
        evidence = {
            source_handle: frame_evidence_digest(frame),
            member.source_handle: member_evidence_digest(frame, member),
        }
        for handle, digest in evidence.items():
            grants.append(SourceGrant(
                handle, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE, digest,
                ("TRAINING",), (REGION,), (SCOPE,),
                rights_epoch=1, correction_generation=1,
                observed_at=0, effective_from=0,
            ))
        frames.append(ContextEligibility(
            frame_handle, frame, source_handle, (member,),
            PRINCIPAL, TENANT, "TRAINING", PUBLIC_FORMAL, RELEASE,
            REGION, SCOPE, PUBLIC_FORMAL, 1, 1, 1, 0, 0, None, index + 1,
        ))
    atoms = tuple(SourceAtom(
        index, f"token{index}", f"source:atom:{index}")
        for index in range(count))
    grants.extend(SourceGrant(
        atom.source_reference, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE,
        atom_evidence_digest(SOURCE_ID, atom, RELEASE),
        ("TRAINING",), (REGION,), (SCOPE,),
        rights_epoch=1, correction_generation=1,
        observed_at=0, effective_from=0,
    ) for atom in atoms)
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda item: item.source_handle)))
    policy = ContextPolicy(
        "synthetic:policy", 1, 1,
        ("TRAINING",), (PUBLIC_FORMAL,), (REGION,), (SCOPE,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        tuple((PUBLIC_FORMAL,) * n for n in range(3, count + 1)),
    )
    task = TaskScope(
        PRINCIPAL, TENANT, "TRAINING", RELEASE, REGION, SCOPE,
        observed_frontier=1, effective_time=1, causal_prefix_end=count,
    )
    approved = project_context(tuple(frames), task, frontier, policy)
    released = tuple(sorted(schemas.values(), key=lambda schema: schema.schema_id))
    config = FrameCompilerConfig(
        released, SchemaTagMap.from_schemas(RELEASE, released),
        approved, task, frontier, policy,
    )
    ast = StreamingAST(
        SOURCE_ID, atoms, tuple(FrameTree(item.frame) for item in frames))
    inventory_grants = []
    for p in range(count + 1):
        compiled = compile_prefix(ast, p, RELEASE, config)
        inventory_grants.append(SourceGrant(
            prefix_inventory_handle(SOURCE_ID, p),
            PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE,
            prefix_inventory_evidence_digest(compiled),
            ("TRAINING",), (REGION,), (SCOPE,),
            rights_epoch=1, correction_generation=1,
            observed_at=0, effective_from=0,
        ))
    frontier = replace(frontier, grants=tuple(sorted(
        (*frontier.grants, *inventory_grants),
        key=lambda item: item.source_handle)))
    config = replace(config, frontier=frontier)
    return SourceCase(tuple(frames), task, frontier, policy, ast, config)


def _grant_salience(frontier, *witnesses):
    extra = tuple(SourceGrant(
        witness.source_handle, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE,
        salience_evidence_digest(witness),
        ("TRAINING",), (REGION,), (SCOPE,),
        rights_epoch=1, correction_generation=1,
        observed_at=0, effective_from=0,
    ) for witness in witnesses)
    return replace(frontier, grants=tuple(sorted(
        (*frontier.grants, *extra), key=lambda item: item.source_handle)))
