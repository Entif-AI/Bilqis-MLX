"""A05.1 causal incremental source-prefix compiler witnesses."""
from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
import socket
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ApprovedContextProjection, ContextEligibility,
    ContextMember, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
    frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_codec import (
    PackDisposition, SchemaTagMap, _canonical_bytes,
)
from bilqis_mlx.semantics.frame_compiler import (
    FrameCompilerConfig, HiddenAnswerTargets, LawfulSourceSegment,
    PositionKind, SourceAtom, StreamingAST, atom_evidence_digest,
    boundary_evidence_digest,
    compile_lawful_segments,
    compile_prefix, compile_prefix_rows, compile_training_example,
    reconstruct,
)
from bilqis_mlx.semantics.frame_schema import (
    AtomicFrame, ChildFrameRef, ConceptRef, FrameSchema, FrameTree,
    RoleOccurrence, RoleSpec, SourceSpan, atomic_fallback,
    make_frame_instance, occurrence_id,
)


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


class FrameCompilerTests(TestCase):
    def test_compact_frame_sidecar_matches_literal_canonical_wire_bytes(self):
        ast, config = _case()
        compiled = compile_prefix(ast, 8, RELEASE, config)
        closure = next(
            item for item in compiled.positions
            if item.kind is PositionKind.CLOSURE)
        actual = _canonical_bytes(asdict(closure.packed.sidecar))
        literal = (
            Path(__file__).parent / "fixtures" / "a05_quad_sidecar.json"
        ).read_bytes()
        self.assertEqual(len(literal), 2563)
        self.assertEqual(
            sha256(literal).hexdigest(),
            "cd2485f302d7e05bea293493e7f697315763fbf0cc8c0df4dbbe99167a7e43fc")
        self.assertEqual(actual, literal)

    def test_first_admission_raw_atom_requires_source_owned_grant(self):
        ast, config = _case()
        first = ast.atoms[0]
        no_frame = replace(config, approved=None)
        ungranted = replace(
            no_frame, frontier=replace(
                no_frame.frontier, grants=tuple(
                    grant for grant in no_frame.frontier.grants
                    if grant.source_handle != first.source_reference)))
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(ast, 1, RELEASE, ungranted)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_ATOM_SOURCE_UNAUTHORIZED")
        revoked = replace(
            no_frame, frontier=replace(
                no_frame.frontier, grants=tuple(
                    replace(grant, revoked=True)
                    if grant.source_handle == first.source_reference else grant
                    for grant in no_frame.frontier.grants)))
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(ast, 1, RELEASE, revoked)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_ATOM_SOURCE_UNAUTHORIZED")
        tampered = replace(
            ast, atoms=(replace(first, token="unattested"), *ast.atoms[1:]))
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(tampered, 1, RELEASE, no_frame)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_ATOM_SOURCE_UNAUTHORIZED")

    def test_hidden_teacher_targets_are_not_model_input_or_cache_identity(self):
        ast, config = _case()
        target_a = HiddenAnswerTargets(
            ast.source_instance_id, (3, 5), (True, True))
        target_b = HiddenAnswerTargets(
            ast.source_instance_id, (9, 0), (True, False))
        first = compile_training_example(
            ast, target_a, 7, RELEASE, config)
        second = compile_training_example(
            ast, target_b, 7, RELEASE, config)
        self.assertEqual(first.input_view, second.input_view)
        self.assertEqual(
            first.input_view.cache_key, second.input_view.cache_key)
        self.assertNotEqual(first.target_view, second.target_view)
        self.assertFalse(hasattr(first.input_view, "target_indices"))
        self.assertFalse(hasattr(first.input_view, "target_view"))

    def test_overflow_fails_before_packing_or_padding(self):
        ast, config = _case()
        extended = replace(
            ast, atoms=ast.atoms + tuple(
                SourceAtom(i, f"extra:{i}", f"source:extra:{i}")
                for i in range(8, 1024)))
        expanded_config = replace(
            config, task=replace(
                config.task, causal_prefix_end=1024))
        with patch(
            "bilqis_mlx.semantics.frame_compiler.pack_frame",
            side_effect=AssertionError("packed before length guard"),
        ):
            with self.assertRaises(BilqisError) as caught:
                compile_prefix(
                    extended, 1024, RELEASE, expanded_config)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")
        atoms_only = replace(
            extended, frames=(), atoms=extended.atoms + (
                SourceAtom(1024, "extra:1024", "source:extra:1024"),))
        with self.assertRaises(BilqisError):
            compile_prefix(
                atoms_only, 1025, RELEASE, replace(
                    expanded_config, approved=None,
                    task=replace(
                        expanded_config.task, causal_prefix_end=1025)))

    def test_exact_1024_neural_positions_are_admitted(self):
        ast, config = _case()
        expanded = replace(
            ast, atoms=ast.atoms + tuple(
                SourceAtom(i, f"extra:{i}", f"source:extra:{i}")
                for i in range(8, 1024)))
        full_config = replace(
            config, task=replace(
                config.task, causal_prefix_end=1024))
        full_config = _with_atom_grants(expanded, full_config)
        atoms_only = compile_prefix(
            replace(expanded, frames=()), 1024, RELEASE,
            replace(full_config, approved=None))
        self.assertEqual(len(atoms_only.positions), 1024)
        self.assertEqual(atoms_only.stats.actual_atoms, 1024)
        self.assertEqual(atoms_only.stats.actual_frames, 0)
        one_frame = compile_prefix(
            replace(expanded, atoms=expanded.atoms[:1023]),
            1023, RELEASE, replace(
                full_config, task=replace(
                    full_config.task, causal_prefix_end=1023)))
        self.assertEqual(len(one_frame.positions), 1024)
        self.assertEqual(
            (one_frame.stats.actual_atoms,
             one_frame.stats.actual_frames), (1023, 1))

    def test_lawful_source_boundaries_split_without_truncation(self):
        _, config = _case()
        segments = []
        for index, (start, end) in enumerate(((0, 800), (800, 1500))):
            ast = StreamingAST(
                f"synthetic:segment:{index}",
                tuple(SourceAtom(
                    local, f"token:{global_index}",
                    f"source:token:{global_index}")
                    for local, global_index in enumerate(
                        range(start, end))), ())
            scoped = replace(
                config, approved=None,
                task=replace(
                    config.task, causal_prefix_end=end - start))
            scoped = _with_atom_grants(ast, scoped)
            segment = LawfulSourceSegment(
                "synthetic:original", SourceSpan(start, end),
                f"source:lawful-boundary:{end}", ast, scoped)
            grant = SourceGrant(
                segment.boundary_source_handle, PRINCIPAL, TENANT,
                PUBLIC_FORMAL, RELEASE, boundary_evidence_digest(segment),
                ("TRAINING",), (REGION,), (SCOPE,),
                rights_epoch=1, correction_generation=1,
                observed_at=2, effective_from=0)
            scoped = replace(
                scoped, frontier=replace(
                    scoped.frontier, grants=tuple(sorted(
                        (*scoped.frontier.grants, grant),
                        key=lambda item: item.source_handle))))
            segments.append(replace(segment, config=scoped))
        compiled = compile_lawful_segments(tuple(segments), RELEASE)
        self.assertEqual(compiled.total_source_atoms, 1500)
        self.assertEqual(compiled.total_neural_positions, 1500)
        self.assertEqual(
            tuple(len(item.positions) for item in compiled.segments),
            (800, 700))
        self.assertEqual(
            compiled.segments[0].positions[0].atom.source_reference,
            "source:token:0")
        self.assertEqual(
            compiled.segments[-1].positions[-1].atom.source_reference,
            "source:token:1499")
        with self.assertRaises(BilqisError):
            compile_lawful_segments((
                segments[0], replace(
                    segments[1], global_span=SourceSpan(801, 1501))),
                RELEASE)
        with self.assertRaises(BilqisError):
            compile_lawful_segments((
                segments[0], replace(
                    segments[1], config=replace(
                        segments[1].config, task=replace(
                            segments[1].config.task,
                            tenant_id="synthetic:other")))),
                RELEASE)
        second = segments[1]
        changed_generation = replace(
            second, config=replace(
                second.config, frontier=replace(
                    second.config.frontier, correction_generation=2,
                    grants=tuple(
                        replace(grant, correction_generation=2)
                        for grant in second.config.frontier.grants))))
        with self.assertRaises(BilqisError) as caught:
            compile_lawful_segments(
                (segments[0], changed_generation), RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_SPLIT_BOUNDARY_INVALID")
        backdated_view = replace(
            second, config=replace(
                second.config, task=replace(
                    second.config.task, observed_frontier=4)))
        with self.assertRaises(BilqisError) as caught:
            compile_lawful_segments(
                (segments[0], backdated_view), RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_SPLIT_BOUNDARY_INVALID")
        ungranted = replace(
            segments[0], config=replace(
                segments[0].config, frontier=replace(
                    segments[0].config.frontier,
                    grants=tuple(
                        grant for grant in segments[0].config.frontier.grants
                        if grant.source_handle
                        != segments[0].boundary_source_handle))))
        with self.assertRaises(BilqisError) as caught:
            compile_lawful_segments((ungranted, segments[1]), RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_SPLIT_SOURCE_UNAUTHORIZED")
        overlong_ast = StreamingAST(
            "synthetic:overlong",
            tuple(SourceAtom(i, f"token:{i}", f"source:token:{i}")
                  for i in range(1025)), ())
        overlong_config = replace(
            config, approved=None,
            task=replace(config.task, causal_prefix_end=1025))
        overlong = LawfulSourceSegment(
            "synthetic:overlong-origin", SourceSpan(0, 1025),
            "source:overlong-boundary", overlong_ast, overlong_config)
        grant = SourceGrant(
            overlong.boundary_source_handle, PRINCIPAL, TENANT,
            PUBLIC_FORMAL, RELEASE, boundary_evidence_digest(overlong),
            ("TRAINING",), (REGION,), (SCOPE,),
            rights_epoch=1, correction_generation=1,
            observed_at=2, effective_from=0)
        overlong = replace(
            overlong, config=replace(
                overlong_config, frontier=replace(
                    overlong_config.frontier, grants=tuple(sorted(
                        (*overlong_config.frontier.grants, grant),
                        key=lambda item: item.source_handle)))))
        with self.assertRaises(BilqisError) as caught:
            compile_lawful_segments((overlong,), RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")

    def test_atom_only_stream_needs_no_future_frame_approval(self):
        ast, config = _case()
        atoms_only = replace(ast, frames=())
        no_frames = replace(config, approved=None)
        for prefix in range(9):
            compiled = compile_prefix(
                atoms_only, prefix, RELEASE, no_frames)
            self.assertEqual(len(compiled.positions), prefix)
            self.assertIsNone(compiled.context_digest)
            self.assertEqual(
                reconstruct(compiled).atoms, ast.atoms[:prefix])
            self.assertEqual(reconstruct(compiled).frames, ())
            self.assertEqual(compiled.stats.actual_frames, 0)
            self.assertEqual(compiled.stats.sidecar_bytes, 0)

    def test_unequal_source_rows_have_separate_positions_and_cache_keys(self):
        ast, config = _case()
        left = compile_prefix(ast, 5, RELEASE, config)
        other = StreamingAST(
            "synthetic:second-row",
            tuple(SourceAtom(i, f"other:{i}", f"source:second:{i}")
                  for i in range(3)),
            ())
        right = compile_prefix(
            other, 3, RELEASE, _with_atom_grants(
                other, replace(
                    config, approved=None,
                    task=replace(config.task, causal_prefix_end=3))))
        self.assertEqual(
            tuple(item.atom.token for item in right.positions),
            ("other:0", "other:1", "other:2"))
        self.assertEqual(len(left.positions), 5)
        self.assertEqual(len(right.positions), 3)
        self.assertNotEqual(left.cache_key, right.cache_key)

    def test_padded_batch_rows_cannot_expose_other_row_or_future_content(self):
        ast, config = _case()
        other = StreamingAST(
            "synthetic:second-row",
            tuple(SourceAtom(i, f"other:{i}", f"source:second:{i}")
                  for i in range(3)), ())
        other_config = replace(
            config, approved=None,
            task=replace(config.task, causal_prefix_end=3))
        other_config = _with_atom_grants(other, other_config)
        batch = compile_prefix_rows((
            (ast, 8, config), (other, 3, other_config)), RELEASE)
        self.assertEqual(len(batch.rows), 2)
        self.assertEqual(tuple(map(len, batch.padded_positions)), (9, 9))
        self.assertEqual(batch.padding_mask[0], (True,) * 9)
        self.assertEqual(
            batch.padding_mask[1], (True,) * 3 + (False,) * 6)
        self.assertEqual(batch.padded_positions[1][3:], (None,) * 6)
        self.assertEqual(
            tuple(position.atom.token
                  for position in batch.padded_positions[1][:3]),
            ("other:0", "other:1", "other:2"))
        self.assertEqual(batch.rows[1].maps.role_access, ())
        self.assertEqual(batch.rows[1].maps.prefix_ends, (0, 1, 2, 3))
        changed_first = replace(
            ast, atoms=tuple(
                replace(atom, token=atom.token + ":changed")
                for atom in ast.atoms))
        altered = compile_prefix_rows((
            (changed_first, 8, _with_atom_grants(changed_first, config)),
            (other, 3, other_config)), RELEASE)
        self.assertEqual(altered.rows[1], batch.rows[1])
        self.assertEqual(altered.padded_positions[1],
                         batch.padded_positions[1])

    def test_exact_source_maps_role_access_expansion_and_prefix_ends(self):
        ast, config = _case()
        partial = compile_prefix(ast, 7, RELEASE, config).maps
        self.assertEqual(partial.prefix_ends, tuple(range(8)))
        self.assertEqual(partial.role_access, ())
        self.assertEqual(partial.expansion_handles, ())
        complete = compile_prefix(ast, 8, RELEASE, config)
        maps = complete.maps
        self.assertEqual(maps.prefix_ends, (
            0, 1, 2, 3, 4, 5, 6, 7, 9))
        self.assertEqual(len(maps.position_to_source), 9)
        self.assertEqual(
            tuple(item.source_reference
                  for item in maps.position_to_source[:8]),
            tuple(atom.source_reference for atom in ast.atoms))
        self.assertEqual(
            maps.position_to_source[8].source_span, SourceSpan(0, 8))
        self.assertEqual(
            maps.source_to_positions[0], (0, 8))
        self.assertEqual(
            maps.source_to_positions[7], (7, 8))
        self.assertEqual(maps.padding_mask, (True,) * 9)
        self.assertEqual(
            tuple(item.role_id for item in maps.role_access),
            ("slot0", "slot1", "slot2", "slot3"))
        self.assertEqual(
            tuple(item.abi_indices for item in maps.role_access),
            ((0,), (1,), (2,), (3,)))
        self.assertEqual(
            tuple(item.source_references for item in maps.role_access),
            tuple((f"source:entity:{i}",) for i in range(4)))
        self.assertEqual(
            maps.expansion_handles[0].frame_handle, "frame:quad:0")
        self.assertEqual(
            maps.scope_boundaries[0].end_position, 9)
        self.assertEqual(
            maps.scope_boundaries[1].scope, "fixture")
        self.assertEqual(
            (complete.stats.actual_atoms,
             complete.stats.actual_frames,
             complete.stats.neural_positions), (8, 1, 9))
        self.assertEqual(complete.stats.disposition_shares, (
            ("COMPACT", 1, 1), ("EXTENDED", 0, 1),
            ("ATOMIC", 0, 1)))
        self.assertGreater(complete.stats.sidecar_bytes, 0)

    def test_policy_version_changes_compiler_digest_even_without_frames(self):
        ast, config = _case()
        original = compile_prefix(ast, 7, RELEASE, config)
        changed = compile_prefix(
            ast, 7, RELEASE, replace(
                config, policy=replace(config.policy, policy_epoch=2)))
        self.assertNotEqual(original.cache_key, changed.cache_key)
        self.assertEqual(original.positions, changed.positions)
        self.assertEqual(original.policy_version[1], 1)
        self.assertEqual(changed.policy_version[1], 2)

    def test_every_four_member_prefix_preserves_only_visible_atoms(self):
        ast, config = _case()
        with patch.object(
            socket, "socket", side_effect=AssertionError("network")
        ):
            for prefix in range(9):
                compiled = compile_prefix(ast, prefix, RELEASE, config)
                visible = reconstruct(compiled)
                self.assertEqual(visible.atoms, ast.atoms[:prefix])
                self.assertEqual(
                    len(visible.frames), 1 if prefix == 8 else 0)
                closures = tuple(
                    position for position in compiled.positions
                    if position.kind is PositionKind.CLOSURE)
                self.assertEqual(len(closures), 1 if prefix == 8 else 0)
                if prefix < 8:
                    self.assertEqual(len(compiled.positions), prefix)
                    self.assertIsNone(compiled.context_digest)
                    self.assertFalse(any(
                        position.frame_handle for position
                        in compiled.positions))
                else:
                    self.assertEqual(
                        closures[0].packed.disposition,
                        PackDisposition.COMPACT)
                    self.assertEqual(
                        visible.frames, ast.frames)

    def test_future_suffix_does_not_change_prior_prefix_or_cache_key(self):
        ast, config = _case()
        for prefix in range(8):
            changed = replace(
                ast, atoms=ast.atoms[:prefix] + tuple(
                    replace(atom, token=atom.token + ":changed")
                    for atom in ast.atoms[prefix:]))
            self.assertEqual(
                compile_prefix(ast, prefix, RELEASE, config),
                compile_prefix(changed, prefix, RELEASE, config))
        before = compile_prefix(ast, 7, RELEASE, config)
        after = compile_prefix(ast, 8, RELEASE, config)
        self.assertEqual(after.positions[:len(before.positions)],
                         before.positions)
        self.assertNotEqual(after.cache_key, before.cache_key)

    def test_future_frame_member_change_cannot_enter_prior_prefix(self):
        ast, config = _case()
        original = ast.frames[0].root
        changed_binding = replace(
            original.bindings[-1], concept=ConceptRef(
                "formal:entity.99", RELEASE, 99, ("Entity",),
                "source:entity:99"))
        changed_frame = make_frame_instance(
            config.schemas[0],
            source_instance_id=original.source_instance_id,
            structural_path=original.structural_path,
            source_span=original.source_span,
            parent_occurrence_id=original.parent_occurrence_id,
            bindings=(*original.bindings[:-1], changed_binding),
            causal_prefix_end=original.causal_prefix_end)
        envelope = replace(
            config.approved.envelopes[0], frame=changed_frame)
        evidence = {
            envelope.source_handle: frame_evidence_digest(changed_frame)}
        evidence.update({
            member.source_handle: member_evidence_digest(
                changed_frame, member)
            for member in envelope.members})
        frontier = replace(
            config.frontier,
            grants=tuple(
                replace(grant, evidence_digest=evidence[grant.source_handle])
                if grant.source_handle in evidence else grant
                for grant in config.frontier.grants))
        approved = project_context(
            (envelope,), config.task, frontier, config.policy)
        self.assertIsInstance(approved, ApprovedContextProjection)
        changed_config = replace(
            config, approved=approved, frontier=frontier)
        changed_ast = replace(ast, frames=(FrameTree(changed_frame),))
        self.assertEqual(
            compile_prefix(ast, 7, RELEASE, config),
            compile_prefix(changed_ast, 7, RELEASE, changed_config))
        self.assertNotEqual(
            compile_prefix(ast, 8, RELEASE, config).cache_key,
            compile_prefix(
                changed_ast, 8, RELEASE, changed_config).cache_key)

    def test_invalid_future_frame_does_not_poison_earlier_prefix(self):
        ast, config = _case()
        malformed_future = FrameTree(
            ast.frames[0].root, (FrameTree(ast.frames[0].root),))
        changed = replace(ast, frames=(malformed_future,))
        self.assertEqual(
            compile_prefix(changed, 7, RELEASE, config),
            compile_prefix(ast, 7, RELEASE, config))
        with self.assertRaises(BilqisError):
            compile_prefix(changed, 8, RELEASE, config)

    def test_nested_child_closes_before_parent_and_atomic_round_trips(self):
        ast, config = _mixed_case()
        self.assertEqual(
            compile_prefix(ast, 8, RELEASE, config),
            compile_prefix(
                replace(ast, frames=tuple(reversed(ast.frames))),
                8, RELEASE, config))
        at_four = reconstruct(compile_prefix(ast, 4, RELEASE, config))
        self.assertEqual(len(at_four.frames), 1)
        self.assertEqual(at_four.frames[0].root.frame_schema_id, "frame:child")
        at_six = reconstruct(compile_prefix(ast, 6, RELEASE, config))
        self.assertEqual(len(at_six.frames), 2)
        self.assertTrue(any(isinstance(tree.root, AtomicFrame)
                            for tree in at_six.frames))
        at_eight = compile_prefix(ast, 8, RELEASE, config)
        closures = tuple(
            position for position in at_eight.positions
            if position.kind is PositionKind.CLOSURE)
        self.assertEqual(len(closures), 3)
        self.assertEqual(tuple(
            position.packed.disposition for position in closures), (
                PackDisposition.EXTENDED,
                PackDisposition.ATOMIC,
                PackDisposition.EXTENDED))
        visible = reconstruct(at_eight)
        parent = next(
            tree for tree in visible.frames
            if getattr(tree.root, "frame_schema_id", None) == "frame:parent")
        self.assertEqual(len(parent.children), 1)
        self.assertEqual(
            parent.children[0].root.frame_schema_id, "frame:child")
        self.assertEqual(visible.atoms, ast.atoms)
        self.assertEqual(at_eight.stats.disposition_shares, (
            ("COMPACT", 0, 3), ("EXTENDED", 2, 3),
            ("ATOMIC", 1, 3)))
        self.assertGreater(at_eight.stats.sidecar_bytes, 0)

    def test_parent_cannot_close_while_child_is_future(self):
        ast, config = _mixed_case()
        child_schema, parent_schema = config.schemas
        source_id = ast.source_instance_id
        original_child = ast.frames[0].children[0].root
        future_child = make_frame_instance(
            child_schema, source_instance_id=source_id,
            structural_path=(0,), source_span=SourceSpan(4, 8),
            parent_occurrence_id=occurrence_id(source_id, ()),
            bindings=original_child.bindings, causal_prefix_end=8)
        early_parent = make_frame_instance(
            parent_schema, source_instance_id=source_id,
            structural_path=(), source_span=SourceSpan(0, 4),
            parent_occurrence_id=None,
            bindings=(RoleOccurrence(
                "child", 0, child_frame=ChildFrameRef(
                    future_child.occurrence_id, future_child.content_digest)),),
            causal_prefix_end=4)
        altered = replace(
            ast, frames=(FrameTree(
                early_parent, (FrameTree(future_child),)),))
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(
                altered, 4, RELEASE, replace(config, approved=None))
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_CHILD_FUTURE")

    def test_revoked_frame_grant_blocks_closure_not_raw_atom_prefix(self):
        ast, config = _case()
        revoked = replace(
            config.frontier,
            grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle == "source:frame:quad" else grant
                for grant in config.frontier.grants))
        blocked = replace(config, frontier=revoked)
        self.assertEqual(
            len(compile_prefix(ast, 7, RELEASE, blocked).positions), 7)
        with self.assertRaises(BilqisError):
            compile_prefix(ast, 8, RELEASE, blocked)

    def test_member_visible_later_moves_closure_without_rewriting_prefix(self):
        ast, config = _case()
        envelope = config.approved.envelopes[0]
        delayed = replace(envelope.members[-1], visible_at_prefix=9)
        delayed_envelope = replace(
            envelope, members=(*envelope.members[:-1], delayed))
        frontier = replace(
            config.frontier,
            grants=tuple(
                replace(
                    grant, evidence_digest=member_evidence_digest(
                        envelope.frame, delayed))
                if grant.source_handle == delayed.source_handle else grant
                for grant in config.frontier.grants))
        task = replace(config.task, causal_prefix_end=10)
        approved = project_context(
            (delayed_envelope,), task, frontier, config.policy)
        self.assertIsInstance(approved, ApprovedContextProjection)
        delayed_config = replace(
            config, approved=approved, task=task, frontier=frontier)
        extended = replace(
            ast, atoms=ast.atoms + (
                SourceAtom(8, "token8", "source:atom:8"),
                SourceAtom(9, "token9", "source:atom:9")))
        delayed_config = _with_atom_grants(extended, delayed_config)
        before = compile_prefix(extended, 8, RELEASE, delayed_config)
        closed = compile_prefix(extended, 9, RELEASE, delayed_config)
        after = compile_prefix(extended, 10, RELEASE, delayed_config)
        self.assertEqual(len(before.positions), 8)
        self.assertEqual(closed.positions[:8], before.positions)
        self.assertEqual(after.positions[:len(closed.positions)],
                         closed.positions)
        closure = next(
            position for position in closed.positions
            if position.kind is PositionKind.CLOSURE)
        self.assertEqual(closure.source_index, 8)
        self.assertEqual(len(reconstruct(closed).frames), 1)

    def test_foreign_release_or_prefix_is_rejected(self):
        ast, config = _case()
        for prefix, release in ((9, RELEASE), (8, "b" * 64), (-1, RELEASE)):
            with self.subTest(prefix=prefix, release=release):
                with self.assertRaises(BilqisError):
                    compile_prefix(ast, prefix, release, config)
