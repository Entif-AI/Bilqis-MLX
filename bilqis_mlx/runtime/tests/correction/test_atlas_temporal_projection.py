"""Source-authenticated temporal projection behavior."""
import unittest
from dataclasses import replace

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.tests.frames.nested_fixtures import _case as _nested_case
from bilqis_mlx.learning.tests.test_frame_encoder import FrameEncoderTests
from bilqis_mlx.runtime.atlas_artifact_owner import PackedFrameArtifactOwner
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, ArtifactKind, DependencyIndex, DependencyKind, TemporalEvent,
    TemporalEventKind, TemporalStatus, _event, _node,
    _ref, apply_correction, bind_as_of_dependency, project_as_of,
    replace,
)
from bilqis_mlx.semantics.frame_compiler import _prefix_digest


class TemporalProjectionTests(unittest.TestCase):
    def test_multi_prefix_rows_share_physical_identity_and_keep_scoped_time(self):
        _ast, _config, compiled, _vectors, _params = _nested_case()
        owner = compiled.packed_frame_artifact_owner
        first = owner.require_row(compiled.compiled.rows[0])
        second = owner.require_row(compiled.compiled.rows[1])
        shared = {node.artifact_id for node in first} & {
            node.artifact_id for node in second}

        self.assertEqual(len(shared), 1)
        shared_id = next(iter(shared))
        first_node = next(node for node in first if node.artifact_id == shared_id)
        second_node = next(node for node in second if node.artifact_id == shared_id)
        self.assertEqual(first_node.content_digest, second_node.content_digest)
        self.assertNotEqual(
            tuple(ref for ref in first_node.immediate_dependencies
                  if ref.kind is DependencyKind.TIME),
            tuple(ref for ref in second_node.immediate_dependencies
                  if ref.kind is DependencyKind.TIME),
        )
        self.assertEqual(len(owner.origin_context_keys), 2)
        self.assertNotIn(
            owner.origin_context_keys[0],
            {node.artifact_id for node in owner.physical_nodes},
        )

    def test_multi_prefix_non_context_drift_still_fails_closed(self):
        _ast, _config, compiled, _vectors, _params = _nested_case()
        first, second = compiled.compiled.rows
        version = (
            first.policy_version[0], first.policy_version[1] + 1,
            first.policy_version[2], first.policy_version[3],
        )
        changed = replace(
            first,
            policy_version=version,
            cache_key=_prefix_digest(
                first.source_instance_id, first.semantic_release,
                first.visible_end, first.schema_map, first.context_digest,
                first.positions, first.scope, version),
        )
        rows = replace(compiled.compiled, rows=(changed, second))

        with self.assertRaises(BilqisError) as caught:
            PackedFrameArtifactOwner(rows)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT",
        )

    def test_multi_prefix_changed_packed_content_still_fails_closed(self):
        _ast, _config, compiled, _vectors, _params = _nested_case()
        first, second = compiled.compiled.rows
        index = next(
            i for i, position in enumerate(first.positions)
            if position.packed is not None)
        position = first.positions[index]
        packed = position.packed
        slot = packed.extended_slots[0]
        changed_slot = replace(
            slot, semantic_ids=("formal:changed",))
        changed_packed = replace(
            packed, extended_slots=(changed_slot, *packed.extended_slots[1:]))
        changed_positions = (
            *first.positions[:index],
            replace(position, packed=changed_packed),
            *first.positions[index + 1:],
        )
        changed = replace(
            first,
            positions=changed_positions,
            cache_key=_prefix_digest(
                first.source_instance_id, first.semantic_release,
                first.visible_end, first.schema_map, first.context_digest,
                changed_positions, first.scope, first.policy_version),
        )
        rows = replace(
            compiled.compiled,
            rows=(changed, second),
            padded_positions=(
                changed_positions
                + compiled.compiled.padded_positions[0][len(changed_positions):],
                compiled.compiled.padded_positions[1],
            ),
        )

        with self.assertRaises(BilqisError) as caught:
            PackedFrameArtifactOwner(rows)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT",
        )

    def test_real_packed_frame_owner_projects_context_time_dependency(self):
        fixture = FrameEncoderTests()
        fixture.setUp()
        compiled, _vectors, _ast = fixture.compiled_inputs()
        owner = compiled.packed_frame_artifact_owner
        context_digests = {
            row.context_digest for row in compiled.compiled.rows
            if row.context_digest is not None
        }
        self.assertTrue(context_digests)
        nodes = owner.index.nodes
        self.assertTrue(nodes)
        for node in nodes:
            time_refs = tuple(
                ref for ref in node.immediate_dependencies
                if ref.kind is DependencyKind.TIME)
            self.assertEqual(len(time_refs), 1)
            self.assertTrue(time_refs[0].key.startswith("time:asof:context:"))
            self.assertIn(time_refs[0].key.removeprefix("time:asof:context:"),
                          context_digests)
        time_ref = next(
            ref for ref in nodes[0].immediate_dependencies
            if ref.kind is DependencyKind.TIME)
        queue = owner.apply_correction(_event(time_ref), AUTHORITY)
        self.assertIn(nodes[0].artifact_id, queue.held_artifact_ids)

    def _temporal_projection_fixture(self):
        planned = TemporalEvent(
            event_id="event:planned", actor_id="actor:alpha",
            kind=TemporalEventKind.PLANNED, fact_digest="a" * 64,
            source_receipt_sha256="1" * 64,
            source_time=570, effective_from=570, effective_until=None,
            observed_at=565, recorded_at=565, expected_report_by=585,
        )
        nonoccurrence = TemporalEvent(
            event_id="event:nonoccurrence", actor_id="actor:alpha",
            kind=TemporalEventKind.EXPLICIT_NONOCCURRENCE,
            fact_digest="b" * 64, source_receipt_sha256="2" * 64,
            source_time=600, effective_from=600, effective_until=None,
            observed_at=601, recorded_at=601,
            supersedes_event_id="event:planned",
        )
        corrected = TemporalEvent(
            event_id="event:corrected", actor_id="actor:alpha",
            kind=TemporalEventKind.CORRECTION, fact_digest="c" * 64,
            source_receipt_sha256="3" * 64,
            source_time=620, effective_from=620, effective_until=None,
            observed_at=621, recorded_at=621,
            supersedes_event_id="event:nonoccurrence",
        )
        return planned, nonoccurrence, corrected

    def test_temporal_projection_distinguishes_plan_silence_negative_and_correction(self):
        planned, nonoccurrence, corrected = self._temporal_projection_fixture()
        events = (planned, nonoccurrence, corrected)
        before = project_as_of(events, actor_id="actor:alpha", as_of=575)
        missing = project_as_of(events, actor_id="actor:alpha", as_of=590)
        explicit = project_as_of(events, actor_id="actor:alpha", as_of=605)
        correction = project_as_of(events, actor_id="actor:alpha", as_of=625)
        self.assertEqual(
            (before.status, missing.status, explicit.status, correction.status),
            (TemporalStatus.PLANNED, TemporalStatus.MISSING_EXPECTED_REPORT,
             TemporalStatus.EXPLICIT_NONOCCURRENCE, TemporalStatus.CORRECTED))
        self.assertEqual(correction.fact_digest, "c" * 64)
        self.assertEqual(missing.fact_digest, "a" * 64)
        self.assertNotEqual(before.time_dependency, missing.time_dependency)
        self.assertEqual(
            project_as_of((planned,), actor_id="actor:alpha", as_of=590),
            missing)
        self.assertEqual(missing.time_dependency.kind, DependencyKind.TIME)
        self.assertEqual(
            project_as_of(events, actor_id="actor:alpha", as_of=567).status,
            TemporalStatus.PLANNED)
        changed_deadline = replace(planned, expected_report_by=600)
        self.assertNotEqual(
            project_as_of((changed_deadline,), actor_id="actor:alpha",
                          as_of=575).time_dependency,
            before.time_dependency)
        expiring = replace(planned, effective_until=580)
        self.assertEqual(
            project_as_of((expiring,), actor_id="actor:alpha",
                          as_of=580).status, TemporalStatus.UNKNOWN)
        self.assertNotEqual(
            project_as_of((expiring,), actor_id="actor:alpha",
                          as_of=575).time_dependency,
            project_as_of((expiring,), actor_id="actor:alpha",
                          as_of=580).time_dependency)
        concurrent = replace(
            corrected, event_id="event:concurrent",
            supersedes_event_id=None, fact_digest="d" * 64)
        self.assertEqual(project_as_of(
            (planned, nonoccurrence, corrected, concurrent),
            actor_id="actor:alpha", as_of=625).status,
            TemporalStatus.CONFLICTING_ALTERNATIVES)
        retroactive = replace(corrected, effective_from=600)
        self.assertEqual(project_as_of(
            (planned, nonoccurrence, retroactive),
            actor_id="actor:alpha", as_of=610).status,
            TemporalStatus.EXPLICIT_NONOCCURRENCE)
        cache = _node("cache:asof", ArtifactKind.EXACT_CACHE, (
            _ref(DependencyKind.SOURCE, "source:plan"),))
        bound = bind_as_of_dependency(cache, before)
        self.assertEqual(apply_correction(
            _event(before.time_dependency),
            DependencyIndex.build((bound,))).held_artifact_ids,
            ("cache:asof",))
        refreshed = bind_as_of_dependency(bound, missing)
        self.assertNotIn(before.time_dependency,
                         refreshed.immediate_dependencies)
        self.assertIn(missing.time_dependency,
                      refreshed.immediate_dependencies)
        actor_a = replace(planned, actor_id="a")
        actor_ab = replace(planned, event_id="event:actor-ab", actor_id="a:b")
        projection_a = project_as_of(
            (actor_a,), actor_id="a", as_of=575)
        projection_ab = project_as_of(
            (actor_ab,), actor_id="a:b", as_of=575)
        both = bind_as_of_dependency(
            bind_as_of_dependency(cache, projection_ab), projection_a)
        rebound = bind_as_of_dependency(
            both, project_as_of((actor_a,), actor_id="a", as_of=590))
        self.assertIn(projection_ab.time_dependency,
                      rebound.immediate_dependencies)

    def test_expiring_intermediate_correction_does_not_resurrect_ancestor(self):
        a = TemporalEvent('a', 'actor:x', TemporalEventKind.OBSERVED,
            'a' * 64, '1' * 64, 10, 10, None, 10, 10)
        b = replace(a, event_id='b', kind=TemporalEventKind.CORRECTION,
            fact_digest='b' * 64, effective_from=20, effective_until=30,
            source_time=20, observed_at=20, recorded_at=20, supersedes_event_id='a')
        c = replace(b, event_id='c', fact_digest='c' * 64, effective_from=25,
            effective_until=None, source_time=25, observed_at=25, recorded_at=25,
            supersedes_event_id='b')
        for time in (26, 31):
            result = project_as_of((a, b, c), actor_id='actor:x', as_of=time)
            self.assertEqual(result.status, TemporalStatus.CORRECTED)
            self.assertEqual(result.fact_digest, 'c' * 64)
