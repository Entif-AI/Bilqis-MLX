"""Test motif read boundaries."""
from bilqis_mlx.learning.tests.test_atlas_engram_reads import (
    ACCESS_SCOPE, AtlasArtifactSelection, BilqisError, ConceptRef,
    ContextEligibility, ContextMember, ContextPolicy, MotifFrameInput,
    MotifManifest, MotifReadPosition, MotifSlot, PUBLIC_FORMAL,
    REAL_BUNDLE, REAL_RELEASE, REAL_SOURCE_BUNDLE, RELEASE,
    RoleOccurrence, SourceFrontier, SourceGrant, SourceSpan,
    TaskScope, TestCase, _parameters, _read,
    _source, frame_evidence_digest, guarded_read_motif, lookup_source_pinned_frame_schema,
    make_frame_instance, member_evidence_digest, motif_keys, mx,
    os, read_motif, replace, unittest,
)


class MotifReadBoundariesTests(TestCase):
    def test_public_read_entrypoint_requires_source_qualified_contract(self):
        with self.assertRaises(TypeError):
            guarded_read_motif()

    @unittest.skipUnless(
        os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
        "real repo-pinned A01 artifact supplied at source turn-in",
    )
    def test_group1_second_read_is_source_qualified_but_quarantined_no_hit(self):
        selection = AtlasArtifactSelection(
            os.environ["BILQIS_ATLAS_REAL_ARTIFACT"],
            REAL_BUNDLE, REAL_RELEASE, REAL_SOURCE_BUNDLE,
        )
        schema, _witness = lookup_source_pinned_frame_schema(
            "frame:legacy:development.op.EDGE", 1,
            source_family="micro", atlas_selection=selection)
        frame = make_frame_instance(
            schema, source_instance_id="synthetic:real-source",
            structural_path=(), source_span=SourceSpan(0, 2),
            parent_occurrence_id=None,
            bindings=(
                RoleOccurrence("arg0", 0, concept=ConceptRef(
                    "formal:alice", REAL_RELEASE, 0, ("Entity",),
                    "source:arg0")),
                RoleOccurrence("arg1", 0, concept=ConceptRef(
                    "formal:bob", REAL_RELEASE, 1, ("Entity",),
                    "source:arg1")),
            ), causal_prefix_end=2,
        )
        members = (
            ContextMember("arg0", 0, "source:member:arg0", 2),
            ContextMember("arg1", 0, "source:member:arg1", 2),
        )
        envelope = ContextEligibility(
            "frame:real:0", frame, "source:frame:real:0", members,
            "synthetic:student", "synthetic:tenant", "TRAINING",
            PUBLIC_FORMAL, REAL_RELEASE, "synthetic:region", ACCESS_SCOPE,
            PUBLIC_FORMAL, 1, 1, 1, 0, 0, None, 2,
        )
        evidence = {
            envelope.source_handle: frame_evidence_digest(frame),
            **{member.source_handle: member_evidence_digest(frame, member)
               for member in members},
        }
        frontier = SourceFrontier(1, 1, tuple(sorted((
            SourceGrant(
                handle, envelope.principal_id, envelope.tenant_id,
                PUBLIC_FORMAL, REAL_RELEASE, digest, ("TRAINING",),
                ("synthetic:region",), (ACCESS_SCOPE,),
                rights_epoch=1, correction_generation=1,
                observed_at=0, effective_from=0)
            for handle, digest in evidence.items()),
            key=lambda grant: grant.source_handle)))
        task = TaskScope(
            envelope.principal_id, envelope.tenant_id, "TRAINING",
            REAL_RELEASE, "synthetic:region", ACCESS_SCOPE, 1, 1, 2)
        policy = ContextPolicy(
            "synthetic:policy", 1, 1, ("TRAINING",),
            (PUBLIC_FORMAL,), ("synthetic:region",), (ACCESS_SCOPE,),
            (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),), ())
        position = MotifReadPosition(envelope, schema, "micro")
        exact, _structural = motif_keys(
            MotifFrameInput(frame, schema), REAL_RELEASE)
        manifest = MotifManifest(REAL_RELEASE, (MotifSlot(0, exact),))
        hidden = mx.arange(2 * 768, dtype=mx.float32).reshape(1, 2, 768)

        result = guarded_read_motif(
            site_index=1, hidden=hidden,
            positions=((position, None),), tasks=(task,),
            frontiers=(frontier,), policies=(policy,), manifest=manifest,
            atlas_selection=selection,
            retained_generation_digest="d" * 64,
            parameter_tree_digest="e" * 64,
        )
        self.assertIs(result.hidden, hidden)
        self.assertEqual(
            result.dispositions, (("QUARANTINED_NO_HIT", "MISS"),))
        self.assertEqual(result.participating_slots, ())
        self.assertEqual(len(result.context_digests[0]), 64)

        forged = replace(position, schema=replace(schema, scope="forged"))
        with self.assertRaises(BilqisError):
            guarded_read_motif(
                site_index=1, hidden=hidden,
                positions=((forged, None),), tasks=(task,),
                frontiers=(frontier,), policies=(policy,), manifest=manifest,
                atlas_selection=selection,
                retained_generation_digest="d" * 64,
                parameter_tree_digest="e" * 64)

        for changed_frontier, changed_task in (
            (replace(frontier, rights_epoch=2), task),
            (replace(frontier, grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle == envelope.source_handle else grant
                for grant in frontier.grants)), task),
            (frontier, replace(task, causal_prefix_end=1)),
        ):
            held = guarded_read_motif(
                site_index=1, hidden=hidden,
                positions=((position, None),), tasks=(changed_task,),
                frontiers=(changed_frontier,), policies=(policy,),
                manifest=manifest, atlas_selection=selection,
                retained_generation_digest="d" * 64,
                parameter_tree_digest="e" * 64)
            self.assertIs(held.hidden, hidden)
            self.assertEqual(held.dispositions, (("HELD", "MISS"),))
            self.assertEqual(held.context_digests, (None,))

        guarded_read_motif(
            site_index=1, hidden=hidden,
            positions=((position, None),), tasks=(task,),
            frontiers=(frontier,), policies=(policy,), manifest=manifest,
            atlas_selection=selection,
            retained_generation_digest="d" * 64,
            parameter_tree_digest="e" * 64,
            expected_cache_digests=result.context_digests)
        with self.assertRaises(BilqisError):
            guarded_read_motif(
                site_index=1, hidden=hidden,
                positions=((position, None),), tasks=(task,),
                frontiers=(frontier,), policies=(policy,), manifest=manifest,
                atlas_selection=selection,
                retained_generation_digest="f" * 64,
                parameter_tree_digest="e" * 64,
                expected_cache_digests=result.context_digests)

    def test_wrong_site_or_invalid_tensor_rejects_before_gather(self):
        position, task, frontier, policy = _source()
        _spec, _extents, _params, view = _parameters()
        with self.assertRaises(BilqisError):
            _read(position, task, frontier, policy, MotifManifest(RELEASE),
                  view, site=1)
        with self.assertRaises(BilqisError):
            read_motif(
                site_index=0,
                hidden=mx.zeros((1, 2, 768), dtype=mx.float32),
                features=mx.ones((1, 2, 127), dtype=mx.float32),
                positions=((position, None),), tasks=(task,),
                frontiers=(frontier,), policies=(policy,),
                manifest=MotifManifest(RELEASE), parameters=view)
