"""Source-authenticated temporal projection behavior."""
import unittest

from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    ArtifactKind, DependencyIndex, DependencyKind, TemporalEvent,
    TemporalEventKind, TemporalStatus, _event, _node,
    _ref, apply_correction, bind_as_of_dependency, project_as_of,
    replace,
)


def _temporal_events():
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
    events = (planned, nonoccurrence, corrected)
    return planned, nonoccurrence, corrected, events


class TemporalProjectionTests(unittest.TestCase):
    def test_temporal_projection_distinguishes_plan_silence_negative_and_correction(self):
        planned, nonoccurrence, corrected, events = _temporal_events()
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
