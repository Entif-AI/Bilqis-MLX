"""Twenty-event append-order salience windows over signed source fixtures."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.salience_history import (
    EventKind, SalienceEvent, SalienceHistory, WindowPolicy,
    append_salience_event, completed_windows,
)
from bilqis_mlx.learning.atlas_salience import derive_salience, verify_salience_inputs
from bilqis_mlx.learning.salience_contracts import AuthoritySnapshot, Metric
from bilqis_mlx.learning.tests.test_atlas_salience import _CONTEXT, _REGISTRY, _policy, _fact, _signed
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry, SourceAuthorityScope
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

_REGISTRY = SourceAuthorityRegistry((replace(_REGISTRY.keys[0], allowed_scopes=tuple(sorted(
    (*_REGISTRY.keys[0].allowed_scopes, SourceAuthorityScope(DependencyKind.ARTIFACT, "salience-event:")),
    key=lambda scope: (scope.kind.value, scope.key_prefix)))),))


def _window_policy(policy):
    return _signed(WindowPolicy("fixture-window", "v1", policy.digest(), _CONTEXT.semantic_release,
                                 3, 1, "fixture:salience-owner", "0" * 128))


def _event(index, policy, *, context=_CONTEXT, lineage=None, kind=EventKind.OBSERVATION,
           observed=None, receipt=None, linked=None, defect=True, before=None, after=None):
    observed = observed if observed is not None else 100 + index
    snapshot = AuthoritySnapshot((context,), observed, _REGISTRY)
    facts = (_fact(Metric.DECLARED_IMPACT, 1, policy, context=context),
             _fact(Metric.BLOCKED_COUNT, 0, policy, context=context))
    evidence = derive_salience(verify_salience_inputs(facts, policy, snapshot, context))
    return _signed(SalienceEvent(
        f"event:{index}", kind, lineage or f"lineage:{index}", f"episode:{index}",
        "1" * 64, "2" * 64, evidence, observed, receipt or f"{index + 1:064x}",
        linked, before, after, None, None, defect, "fixture:salience-owner", "0" * 128))


def _append(history, event):
    return append_salience_event(history, event, event.evidence.basis.snapshot)


class SalienceWindowTests(unittest.TestCase):
    def test_nineteen_twenty_twentyone_and_exact_replay(self):
        policy = _policy()
        history = SalienceHistory(_window_policy(policy), ())
        for index in range(19):
            history = _append(history, _event(index, policy))
        self.assertEqual(completed_windows(history), ())
        last = _event(19, policy)
        history = _append(history, last)
        window = completed_windows(history)[0]
        self.assertEqual(len(window.events), 20)
        self.assertEqual(len(window.procedure_candidates), 1)
        self.assertEqual(window.procedure_candidates[0].independent_lineages, 20)
        self.assertFalse(window.procedure_candidates[0].source_gold)
        self.assertFalse(window.procedure_candidates[0].qualified_for_teaching)
        self.assertEqual(_append(history, last), history)
        with self.assertRaises(BilqisError):
            _append(history, _signed(replace(last, lineage_id="different")))
        extended = _append(history, _event(20, policy))
        self.assertEqual(completed_windows(extended), (window,))

    def test_paraphrase_lineage_does_not_mint_a_process_candidate(self):
        policy = _policy()
        history = SalienceHistory(_window_policy(policy), ())
        for index in range(20):
            history = _append(history, _event(index, policy, lineage="one-source"))
        self.assertEqual(completed_windows(history)[0].procedure_candidates, ())

    def test_interleaved_epochs_and_late_events_never_rewrite_closed_window(self):
        policy = _policy()
        history = SalienceHistory(_window_policy(policy), ())
        other = replace(_CONTEXT, capability_epoch="3" * 64)
        for index in range(40):
            history = _append(history, _event(index, policy, context=_CONTEXT if index % 2 == 0 else other))
        windows = completed_windows(history)
        self.assertEqual(len(windows), 2)
        late = _event(40, policy, observed=101)
        history = _append(history, late)
        self.assertEqual(completed_windows(history), windows)
        with self.assertRaises(BilqisError):
            append_salience_event(history, _event(41, policy, context=other),
                                  AuthoritySnapshot((_CONTEXT,), 200, _REGISTRY))

    def test_followups_require_exact_receipt_and_explicit_observations(self):
        policy = _policy()
        history = SalienceHistory(_window_policy(policy), ())
        correction = _event(0, policy, kind=EventKind.CORRECTION_APPLIED, defect=None)
        history = _append(history, correction)
        lesson = _event(1, policy, kind=EventKind.ACCEPTED_LESSON, defect=None)
        history = _append(history, lesson)
        changed = _event(2, policy, kind=EventKind.FOLLOWUP, linked=lesson.source_receipt_sha256,
                         defect=None, before="4" * 64, after="5" * 64)
        history = _append(history, changed)
        clean = _event(3, policy, kind=EventKind.FOLLOWUP,
                       linked=correction.source_receipt_sha256, defect=False)
        history = _append(history, clean)
        for index in range(4, 20):
            history = _append(history, _event(index, policy, defect=None))
        window = completed_windows(history)[0]
        self.assertEqual(window.accepted_lesson_count, 1)
        self.assertEqual(window.changed_actions, 1)
        self.assertEqual(window.correction_followups[0].status, "NO_RECURRENCE_IN_MEASURED_FOLLOWUP")

    def test_equal_time_followup_is_not_a_later_measured_effect(self):
        policy = _policy()
        history = SalienceHistory(_window_policy(policy), ())
        correction = _event(0, policy, kind=EventKind.CORRECTION_APPLIED, observed=100, defect=None)
        history = _append(history, correction)
        history = _append(history, _event(1, policy, kind=EventKind.FOLLOWUP, observed=100,
                                         linked=correction.source_receipt_sha256, defect=False))
        for index in range(2, 20):
            history = _append(history, _event(index, policy, defect=None))
        self.assertEqual(completed_windows(history)[0].correction_followups[0].status, "NOT_MEASURED")

    def test_revoked_fact_signer_cannot_hide_behind_valid_event_signer(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityKey
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("55" * 32))
        fact_owner = SourceAuthorityKey("fixture:fact-owner",
            key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
            (SourceAuthorityScope(DependencyKind.ARTIFACT, "salience-fact:"),
             SourceAuthorityScope(DependencyKind.SOURCE, "salience-fact:")))
        registry = SourceAuthorityRegistry(tuple(sorted((*_REGISTRY.keys, fact_owner), key=lambda item: item.owner_id)))
        policy = _policy()
        original = _event(0, policy)
        facts = []
        for fact in original.evidence.basis.facts:
            fact = replace(fact, source_owner=fact_owner.owner_id)
            facts.append(replace(fact, signature_hex=key.sign(fact.signing_bytes()).hex()))
        snapshot = AuthoritySnapshot((_CONTEXT,), 100, registry)
        evidence = derive_salience(verify_salience_inputs(tuple(facts), policy, snapshot, _CONTEXT))
        event = _signed(replace(original, evidence=evidence))
        history = SalienceHistory(_window_policy(policy), ())
        self.assertEqual(len(append_salience_event(history, event, snapshot).events), 1)
        with self.assertRaises(BilqisError):
            append_salience_event(history, event, AuthoritySnapshot((_CONTEXT,), 100, _REGISTRY))
