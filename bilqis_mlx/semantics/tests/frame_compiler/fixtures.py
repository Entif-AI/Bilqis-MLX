"""Source-owned quad and nested-forest compiler fixtures."""
from __future__ import annotations
from dataclasses import replace
from bilqis_mlx.semantics.context_eligibility import PUBLIC_FORMAL, ApprovedContextProjection, ContextEligibility, ContextMember, ContextPolicy, SourceFrontier, SourceGrant, TaskScope, frame_evidence_digest, member_evidence_digest, project_context
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import FrameCompilerConfig, SourceAtom, StreamingAST, atom_evidence_digest
from bilqis_mlx.semantics.frame_schema import AtomicFrame, ChildFrameRef, ConceptRef, FrameSchema, FrameTree, RoleOccurrence, RoleSpec, SourceSpan, atomic_fallback, make_frame_instance, occurrence_id


RELEASE = "a" * 64



PRINCIPAL = "synthetic:alice"



TENANT = "synthetic:tenant"



REGION = "synthetic:region"



SCOPE = "synthetic:public"



def _with_atom_grants(ast, config):
    """Source fixture grants exact raw atoms, independently of frame grants."""
    grants = {item.source_handle: item for item in config.frontier.grants}
    for atom in ast.atoms:
        digest = atom_evidence_digest(ast.source_instance_id, atom, RELEASE)
        existing = grants.get(atom.source_reference)
        grants[atom.source_reference] = (
            replace(existing, evidence_digest=digest)
            if existing is not None else SourceGrant(
                atom.source_reference, PRINCIPAL, TENANT,
                PUBLIC_FORMAL, RELEASE, digest,
                ("TRAINING",), (REGION,), (SCOPE,),
                rights_epoch=config.frontier.rights_epoch,
                correction_generation=config.frontier.correction_generation,
                observed_at=2, effective_from=0))
    return replace(
        config, frontier=replace(
            config.frontier,
            grants=tuple(sorted(
                grants.values(), key=lambda item: item.source_handle))))



def _case():
    schema = FrameSchema(
        "frame:quad", 1, "source:quad",
        tuple(RoleSpec(f"slot{i}", ("Entity",), 1, 1)
              for i in range(4)),
        "ORDERED", "fixture")
    source_id = "synthetic:source"
    frame = make_frame_instance(
        schema, source_instance_id=source_id,
        structural_path=(), source_span=SourceSpan(0, 8),
        parent_occurrence_id=None,
        bindings=tuple(
            RoleOccurrence(
                role.role_id, 0,
                concept=ConceptRef(
                    f"formal:entity.{i}", RELEASE, i,
                    ("Entity",), f"source:entity:{i}"))
            for i, role in enumerate(schema.roles)),
        causal_prefix_end=8)
    members = tuple(
        ContextMember(role.role_id, 0, f"source:member:{i}", 8)
        for i, role in enumerate(schema.roles))
    envelope = ContextEligibility(
        "frame:quad:0", frame, "source:frame:quad", members,
        PRINCIPAL, TENANT, "TRAINING", PUBLIC_FORMAL, RELEASE,
        REGION, SCOPE, PUBLIC_FORMAL, 1, 1, 1, 2, 0, None, 8)
    evidence = {envelope.source_handle: frame_evidence_digest(frame)}
    evidence.update({
        member.source_handle: member_evidence_digest(frame, member)
        for member in members})
    grants = tuple(sorted(
        (SourceGrant(
            handle, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE, digest,
            ("TRAINING",), (REGION,), (SCOPE,),
            rights_epoch=1, correction_generation=1,
            observed_at=2, effective_from=0)
         for handle, digest in evidence.items()),
        key=lambda item: item.source_handle))
    task = TaskScope(
        PRINCIPAL, TENANT, "TRAINING", RELEASE, REGION, SCOPE,
        observed_frontier=3, effective_time=5, causal_prefix_end=8)
    policy = ContextPolicy(
        "synthetic:policy", 1, 1, ("TRAINING",),
        (PUBLIC_FORMAL,), (REGION,), (SCOPE,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL, PUBLIC_FORMAL),))
    frontier = SourceFrontier(1, 1, grants)
    approved = project_context((envelope,), task, frontier, policy)
    assert isinstance(approved, ApprovedContextProjection)
    config = FrameCompilerConfig(
        (schema,), SchemaTagMap.from_schemas(RELEASE, (schema,)),
        approved, task, frontier, policy)
    ast = StreamingAST(
        source_id,
        tuple(SourceAtom(i, f"token{i}", f"source:atom:{i}")
              for i in range(8)),
        (FrameTree(frame),))
    return ast, _with_atom_grants(ast, config)



def _mixed_case():
    base_ast, base_config = _case()
    source_id = base_ast.source_instance_id
    child_schema = FrameSchema(
        "frame:child", 1, "source:child",
        (RoleSpec("subject", ("Entity",), 1, 1),),
        "ORDERED", "fixture")
    parent_schema = FrameSchema(
        "frame:parent", 1, "source:parent",
        (RoleSpec("child", ("Frame",), 1, 1),),
        "ORDERED", "fixture")
    child = make_frame_instance(
        child_schema, source_instance_id=source_id,
        structural_path=(0,), source_span=SourceSpan(0, 4),
        parent_occurrence_id=occurrence_id(source_id, ()),
        bindings=(RoleOccurrence(
            "subject", 0, concept=ConceptRef(
                "formal:entity.1", RELEASE, 1, ("Entity",),
                "source:entity:1")),),
        causal_prefix_end=4)
    parent = make_frame_instance(
        parent_schema, source_instance_id=source_id,
        structural_path=(), source_span=SourceSpan(0, 8),
        parent_occurrence_id=None,
        bindings=(RoleOccurrence(
            "child", 0, child_frame=ChildFrameRef(
                child.occurrence_id, child.content_digest)),),
        causal_prefix_end=8)
    atomic = atomic_fallback(
        {"kind": "token", "value": "x"},
        source_instance_id=source_id, structural_path=(1,),
        source_span=SourceSpan(4, 6),
        parent_occurrence_id=None, causal_prefix_end=6)
    frames = (child, atomic, parent)
    envelopes = []
    grants = []
    for index, frame in enumerate(frames):
        handle = f"frame:mixed:{index}"
        source = f"source:frame:mixed:{index}"
        keys = (
            tuple(binding.key for binding in frame.bindings)
            if not isinstance(frame, AtomicFrame) else (("<atomic>", 0),))
        members = tuple(
            ContextMember(
                role, occurrence, f"source:member:mixed:{index}:{slot}",
                frame.causal_prefix_end)
            for slot, (role, occurrence) in enumerate(keys))
        envelope = ContextEligibility(
            handle, frame, source, members,
            PRINCIPAL, TENANT, "TRAINING", PUBLIC_FORMAL, RELEASE,
            REGION, SCOPE, PUBLIC_FORMAL, 1, 1, 1, 2, 0, None,
            frame.causal_prefix_end)
        envelopes.append(envelope)
        evidence = {source: frame_evidence_digest(frame)}
        evidence.update({
            member.source_handle: member_evidence_digest(frame, member)
            for member in members})
        grants.extend(
            SourceGrant(
                name, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE, digest,
                ("TRAINING",), (REGION,), (SCOPE,),
                rights_epoch=1, correction_generation=1,
                observed_at=2, effective_from=0)
            for name, digest in evidence.items())
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda item: item.source_handle)))
    approved = project_context(
        tuple(envelopes), base_config.task, frontier, base_config.policy)
    assert isinstance(approved, ApprovedContextProjection)
    schemas = (child_schema, parent_schema)
    config = FrameCompilerConfig(
        schemas, SchemaTagMap.from_schemas(RELEASE, schemas),
        approved, base_config.task, frontier, base_config.policy)
    ast = replace(base_ast, frames=(
        FrameTree(parent, (FrameTree(child),)), FrameTree(atomic)))
    return ast, _with_atom_grants(ast, config)
