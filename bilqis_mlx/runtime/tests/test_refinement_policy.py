"""B06.2 complete A05 prefix plus A13 source-gated prediction-local policy."""
from __future__ import annotations

from dataclasses import dataclass, replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.refinement_policy import (
    RefinementSelection, SourceSalience, salience_evidence_digest,
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


class RefinementPolicyTests(unittest.TestCase):
    def test_quota_8_to_9_and_future_frames_do_not_change_earlier_prediction(self):
        case = _case()
        early = replace(case.task, causal_prefix_end=8)
        before = case.select(frames=case.frames[:8], task=early)
        appended = case.select(task=early)
        self.assertEqual(before, appended)
        self.assertEqual((before.eligible_count, before.quota), (8, 1))
        self.assertEqual(tuple(x.frame_handle for x in before.selected), ("frame:4",))
        self.assertEqual(before.selected[0].passes, 1)
        later = case.select()
        self.assertEqual((later.eligible_count, later.quota), (9, 2))
        self.assertEqual(tuple(x.frame_handle for x in later.selected),
                         ("frame:4", "frame:8"))
        self.assertEqual(len(later.remaining_frame_handles), 7)
        self.assertEqual(later.selected[0].cache_identity,
                         ("generation:1", 9, "query:1",
                          case.frames[4].frame.occurrence_id))

    def test_missing_eligible_visible_frame_cannot_shrink_quota(self):
        case = _case()
        with self.assertRaises(BilqisError):
            case.select(frames=case.frames[:8])
        with self.assertRaises(BilqisError):
            case.select(frames=())
        self.assertEqual(case.select().quota, 2)

    def test_role_priority_then_attested_salience_then_source_order(self):
        case = _case()
        approved = project_context(
            case.frames, case.task, case.frontier, case.policy)
        by_handle = {item.frame_handle: item for item in approved.eligible.frames}
        signals = (
            SourceSalience("frame:0", "source:salience:0",
                           by_handle["frame:0"].envelope_digest, 1, 100.0),
            SourceSalience("frame:8", "source:salience:8",
                           by_handle["frame:8"].envelope_digest, 9, 5.0),
        )
        result = case.select(
            frontier=_grant_salience(case.frontier, *signals),
            source_salience=signals)
        self.assertEqual(tuple(x.frame_handle for x in result.selected),
                         ("frame:8", "frame:4"))
        self.assertEqual([x.role_matches for x in result.selected], [1, 1])
        plain = case.select(requested_roles=("other",))
        self.assertEqual(tuple(x.frame_handle for x in plain.selected),
                         ("frame:0", "frame:1"))

    def test_seed_samples_all_passes_independent_of_future_context(self):
        case = _case()
        early = replace(case.task, causal_prefix_end=8)
        seen = set()
        for index in range(48):
            args = dict(training=True, visit_id=f"visit:{index}", task=early)
            a = case.select(frames=case.frames[:8], **args)
            b = case.select(**args)
            self.assertEqual(a, b)
            seen.add(a.selected[0].passes)
        self.assertEqual(seen, {0, 1, 2})
        self.assertEqual(case.select(
            task=early, explicit_member_question=False).selected[0].passes, 0)
        self.assertEqual(case.select(
            task=early, unresolved_nested_query=True).selected[0].passes, 2)

    def test_revoked_source_and_forged_salience_reject(self):
        case = _case(count=1, target_indices=(0,))
        revoked = replace(case.frontier, grants=tuple(
            replace(grant, revoked=True)
            if grant.source_handle == "source:frame:0" else grant
            for grant in case.frontier.grants))
        held = case.select(frontier=revoked)
        self.assertIsInstance(held, ContextHold)
        self.assertIn("BAMF_CONTEXT_SOURCE_REVOKED", held.reason_codes)
        approved = project_context(
            case.frames, case.task, case.frontier, case.policy)
        witness = SourceSalience(
            "frame:0", "source:salience:0",
            approved.eligible.frames[0].envelope_digest, 1, 1.0)
        attested = _grant_salience(case.frontier, witness)
        self.assertEqual(case.select(
            frontier=attested, source_salience=(witness,)
        ).selected[0].salience, 1.0)
        for bad in (replace(witness, envelope_digest="b"*64),
                    replace(witness, visible_at_prefix=2)):
            with self.assertRaises(BilqisError):
                case.select(frontier=attested, source_salience=(bad,))
        with self.assertRaises(BilqisError):
            case.select(source_salience=(witness,))
        revoked_signal = replace(attested, grants=tuple(
            replace(grant, revoked=True)
            if grant.source_handle == witness.source_handle else grant
            for grant in attested.grants))
        with self.assertRaises(BilqisError):
            case.select(frontier=revoked_signal, source_salience=(witness,))

    def test_future_salience_and_padding_do_not_affect_earlier_view(self):
        case = _case()
        early = replace(case.task, causal_prefix_end=8)
        approved = project_context(
            case.frames, case.task, case.frontier, case.policy)
        witness = SourceSalience(
            "frame:8", "source:salience:8",
            next(x.envelope_digest for x in approved.eligible.frames
                 if x.frame_handle == "frame:8"), 9, 1000.0)
        before = case.select(frames=case.frames[:8], task=early)
        after = case.select(
            task=early, frontier=_grant_salience(case.frontier, witness),
            source_salience=(witness,))
        self.assertEqual(before, after)
        self.assertEqual(
            case.select(task=replace(case.task, causal_prefix_end=0)),
            RefinementSelection("generation:1", 0, "query:1", None, 0, 0, (), ()))

    def test_invalid_inputs_reject(self):
        case = _case(count=1, target_indices=(0,))
        for changes in (
            {"training": 1},
            {"requested_roles": ("target", "target")},
            {"explicit_member_question": True, "requested_roles": ()},
            {"input_generation": ""},
            {"source_salience": (SourceSalience(
                "unknown", "source:salience:unknown", "a"*64, 0, 1.0),)},
            {"compiler_config": replace(case.config, policy=replace(
                case.policy, policy_epoch=2))},
        ):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                case.select(**changes)


if __name__ == "__main__":
    unittest.main()
