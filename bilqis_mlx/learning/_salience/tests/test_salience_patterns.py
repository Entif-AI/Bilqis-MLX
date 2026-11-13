"""Independent minor discrepancies nominate conjectures, never source gold."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.salience_patterns import (
    AggregationPolicy, ObservationAnnotation, aggregate_salience_patterns,
)
from bilqis_mlx.learning.salience_history import SalienceHistory, append_salience_event
from bilqis_mlx.learning.tests.test_salience_history import _window_policy, _event, _REGISTRY
from bilqis_mlx.learning.tests.test_atlas_salience import _CONTEXT, _policy, _signed
from bilqis_mlx.learning.salience_contracts import AuthoritySnapshot
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry, SourceAuthorityScope
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

_REGISTRY = SourceAuthorityRegistry((replace(_REGISTRY.keys[0], allowed_scopes=tuple(sorted(
    (*_REGISTRY.keys[0].allowed_scopes, SourceAuthorityScope(DependencyKind.ARTIFACT, 'salience-annotation:')),
    key=lambda scope: (scope.kind.value, scope.key_prefix)))),))


def _history(count, *, same_lineage=False, unrelated=False):
    policy = _policy()
    history = SalienceHistory(_window_policy(policy), ())
    for index in range(count):
        event = _event(index, policy, lineage='one-source' if same_lineage else None)
        if unrelated:
            event = _signed(replace(event, defect_sha256=f'{index + 10:064x}'))
        history = append_salience_event(history, event, event.evidence.basis.snapshot)
    return history


def _aggregation_policy(history, *, minimum=3):
    return _signed(AggregationPolicy('patterns', 'v1', history.policy.digest(), minimum, 2, 1,
                                     1, 'fixture:salience-owner', '0' * 128))


def _snapshot(*, revoked=False):
    return AuthoritySnapshot((replace(_CONTEXT, rights_epoch=2) if revoked else _CONTEXT,), 1000, _REGISTRY)


class SaliencePatternTests(unittest.TestCase):
    def test_independent_minor_events_form_one_conjecture_with_full_provenance(self):
        history = _history(20)
        event = history.events[0]
        annotation = _signed(ObservationAnnotation('claim-one', event.digest(), '4' * 64,
            ('5' * 64, '6' * 64), 'fixture:salience-owner', '0' * 128))
        result = aggregate_salience_patterns(history, _aggregation_policy(history), (annotation,), _snapshot())
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(len(result.patterns), 1)
        pattern = result.patterns[0]
        self.assertEqual(pattern.status, 'CONJECTURE')
        self.assertEqual(pattern.independent_lineages, 20)
        self.assertEqual(pattern.events, history.events)
        self.assertEqual(pattern.observed_time_bounds, (100, 119))
        self.assertEqual(pattern.annotations, (annotation,))
        self.assertEqual(pattern.alternative_explanation_digests, ('5' * 64, '6' * 64))
        self.assertEqual(len(pattern.missing_annotation_event_ids), 19)
        self.assertFalse(pattern.source_gold)
        self.assertFalse(pattern.qualified_for_teaching)
        self.assertEqual(result.investigation_pattern_ids, (pattern.pattern_id,))
        self.assertFalse(hasattr(result, 'training_rows'))
        self.assertFalse(hasattr(result, 'teacher_options'))

    def test_paraphrases_and_unrelated_defects_do_not_mint_independence(self):
        for history in (_history(20, same_lineage=True), _history(20, unrelated=True), _history(1)):
            result = aggregate_salience_patterns(history, _aggregation_policy(history), (), _snapshot())
            self.assertEqual(result.patterns, ())
            self.assertEqual(result.investigation_pattern_ids, ())

    def test_versioned_union_spans_windows_without_recounting_roots(self):
        history = _history(40)
        # Each completed window has only two independent roots, below window threshold3.
        events = tuple(_signed(replace(event, lineage_id=f'root:{index // 20}:{index % 2}'))
                       for index, event in enumerate(history.events))
        history = replace(history, events=events)
        result = aggregate_salience_patterns(history, _aggregation_policy(history), (), _snapshot())
        self.assertEqual(len(result.clusters), 2)
        self.assertEqual(result.patterns[0].independent_lineages, 4)
        self.assertEqual(tuple(point.new_lineages for point in result.trends[0].points), (2, 2))
        self.assertTrue(result.trends[0].supported)
        repeated = replace(history, events=tuple(_signed(replace(event, lineage_id=f'root:{index % 2}'))
                                                 for index, event in enumerate(events)))
        result = aggregate_salience_patterns(repeated, _aggregation_policy(repeated, minimum=2), (), _snapshot())
        self.assertEqual(result.patterns[0].independent_lineages, 2)
        self.assertEqual(tuple(point.new_lineages for point in result.trends[0].points), (2, 0))
        self.assertFalse(result.trends[0].supported)
        self.assertEqual(len(result.investigation_pattern_ids), 1)

    def test_stable_identity_separate_from_evidence_and_revocation_holds(self):
        history = _history(40)
        first = replace(history, events=history.events[:20])
        policy = _aggregation_policy(history)
        early = aggregate_salience_patterns(first, policy, (), _snapshot())
        later = aggregate_salience_patterns(history, policy, (), _snapshot())
        self.assertEqual(early.patterns[0].pattern_id, later.patterns[0].pattern_id)
        self.assertNotEqual(early.patterns[0].evidence_digest, later.patterns[0].evidence_digest)
        held = aggregate_salience_patterns(history, policy, (), _snapshot(revoked=True))
        self.assertEqual(held.patterns, later.patterns)
        self.assertEqual(held.investigation_pattern_ids, ())
        self.assertEqual(held.holds, ((later.patterns[0].pattern_id, 'CURRENT_SOURCE_OR_RIGHTS_HELD'),))
        key = replace(_REGISTRY.keys[0], allowed_scopes=tuple(scope for scope in _REGISTRY.keys[0].allowed_scopes
                      if not (scope.kind is DependencyKind.SOURCE and scope.key_prefix == 'salience-fact:')))
        current = AuthoritySnapshot((_CONTEXT,), 1000, SourceAuthorityRegistry((key,)))
        self.assertEqual(aggregate_salience_patterns(history, policy, (), current).investigation_pattern_ids, ())

    def test_invalid_signatures_unknown_annotations_and_divergent_ids_are_errors(self):
        history = _history(20)
        event = history.events[0]
        annotation = _signed(ObservationAnnotation('claim-one', event.digest(), '4' * 64,
            ('5' * 64,), 'fixture:salience-owner', '0' * 128))
        for annotations in ((replace(annotation, signature_hex='0' * 128),),
                            (_signed(replace(annotation, event_digest='8' * 64)),),
                            (annotation, _signed(replace(annotation, conjecture_digest='7' * 64)))):
            with self.assertRaises(BilqisError):
                aggregate_salience_patterns(history, _aggregation_policy(history), annotations, _snapshot())
        with self.assertRaises(BilqisError):
            replace(history, events=(replace(event, signature_hex='0' * 128), *history.events[1:]))
