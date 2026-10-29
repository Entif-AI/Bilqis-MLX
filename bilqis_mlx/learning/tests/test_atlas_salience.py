"""Signed salience fixtures and literal B01 head projections; no student state."""
from dataclasses import replace
import unittest
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_salience import (
    derive_salience, project_salience_heads, verify_salience_inputs,
    rank_attention_options,
)
from bilqis_mlx.learning.salience_contracts import (
    ActionKind, AttentionOption, AuthoritySnapshot, FactOrigin, Metric, MetricRule,
    NoveltyComparison, NoveltyState, ObservationState, Ordinal, SalienceContext,
    SaliencePolicy, Signal, SignedFact,
)
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, GenerationExtents, expected_bamf_shapes
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

# Public fixture key; never used as a source or operator credential.
_KEY = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("44" * 32))
_OWNER = "fixture:salience-owner"
_REGISTRY = SourceAuthorityRegistry((SourceAuthorityKey(
    _OWNER, _KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
    tuple(sorted((SourceAuthorityScope(DependencyKind.POLICY, "salience-policy:"),
                  SourceAuthorityScope(DependencyKind.SOURCE, "salience-fact:"),
                  SourceAuthorityScope(DependencyKind.ARTIFACT, "salience-fact:"),
                  SourceAuthorityScope(DependencyKind.ARTIFACT, "salience-option:")),
                 key=lambda scope: (scope.kind.value, scope.key_prefix)))),))
_CONTEXT = SalienceContext("a" * 64, "b" * 64, 1, 1, "capability:one", "c" * 64,
                           "scope:one", "family:fixture", "d" * 64, "e" * 64)


def _signed(record):
    return replace(record, signature_hex=_KEY.sign(record.signing_bytes()).hex())


def _policy():
    count_metrics = (Metric.DOWNSTREAM_COUNT, Metric.COVERAGE_COUNT,
                     Metric.BLOCKED_COUNT, Metric.REPAIR_COUNT)
    rules = (MetricRule(Metric.DECLARED_IMPACT, "ordinal-index", (1, 2, 3, 4), tuple(Ordinal), "declared/v1"),
             MetricRule(Metric.DEADLINE_AT, "seconds-until-deadline", (1, 61, 3601),
                        (Ordinal.CRITICAL, Ordinal.HIGH, Ordinal.MODERATE, Ordinal.LOW), "deadline/v1"),
             *(MetricRule(metric, "count", (1, 3, 8),
                          (Ordinal.LOW, Ordinal.MODERATE, Ordinal.HIGH, Ordinal.CRITICAL), metric.value + "/v1")
               for metric in count_metrics))
    return _signed(SaliencePolicy(
        "fixture", "v1", _CONTEXT.semantic_release, ("family:fixture",), rules,
        ((NoveltyState.MATCHED, Ordinal.LOW), (NoveltyState.STRUCTURE_CHANGED, Ordinal.MODERATE),
         (NoveltyState.OUTCOME_CHANGED, Ordinal.HIGH), (NoveltyState.EXPECTED_MISSING, Ordinal.CRITICAL),
         (NoveltyState.REPORTED_NEGATIVE, Ordinal.LOW)),
        ((Signal.IMPACT, (Metric.DECLARED_IMPACT,)),
         (Signal.EXIGENCY, (Metric.BLOCKED_COUNT,)),
         (Signal.NOVELTY, (Metric.NOVELTY_COMPARISON,))),
        1, _OWNER, "0" * 128))


def _fact(metric, value, policy, *, context=_CONTEXT, observed_at=50, origin=FactOrigin.OUTCOME):
    if metric in (Metric.DECLARED_IMPACT, Metric.IMPACT_UNKNOWN, Metric.EXIGENCY_UNKNOWN, Metric.NOVELTY_UNKNOWN):
        origin = FactOrigin.SOURCE
    return _signed(SignedFact(metric.value, metric, value, origin, context, policy.digest(),
                              "f" * 64, 40, 40, observed_at, observed_at + 1, _OWNER, "0" * 128))


def _derive(facts, policy=None, context=_CONTEXT, as_of=100):
    policy = policy or _policy()
    snapshot = AuthoritySnapshot((context,), as_of, _REGISTRY)
    return derive_salience(verify_salience_inputs(tuple(facts), policy, snapshot, context))


def _novelty(state=ObservationState.OBSERVED, **kwargs):
    return NoveltyComparison("expectation:one", "1" * 64, "2" * 64, 10, 80,
                             "event:one" if state is not ObservationState.EXPECTED_MISSING else None,
                             "1" * 64 if state is ObservationState.OBSERVED else None,
                             "2" * 64 if state is ObservationState.OBSERVED else None, state, **kwargs)


def _option(name, evidence, *, action=ActionKind.TEACHING, age=20, admissible=True,
            rights=True, ready=True, relevant=False, unlocks=0, correction=False, exploration=False):
    return _signed(AttentionOption(name, evidence.scope, evidence.basis.digest(), action,
                                   age, admissible, rights, ready, relevant, unlocks,
                                   correction, exploration, _OWNER, "0" * 128))


class AtlasSalienceTests(unittest.TestCase):
    def test_sparse_fp32_logits_use_all_six_normative_tensors(self):
        topology = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
        specs = [spec for spec in expected_bamf_shapes(topology, extents)
                 if spec.name.startswith(("readout.salience.", "readout.salience_bias."))]
        parameters = {spec.name: np.zeros(spec.shape, dtype=np.float32) for spec in specs}
        for multiplier, signal in enumerate(("impact", "exigency", "novelty"), 1):
            weights = parameters["readout.salience." + signal]
            weights[:, 1] = np.arange(1, 6, dtype=np.float32) * multiplier
            weights[:, 7] = multiplier
            parameters["readout.salience_bias." + signal][:] = np.arange(5, dtype=np.float32)
        hidden = np.zeros((1, 2, 768), dtype=np.float32)
        hidden[0, 0, 1], hidden[0, 0, 7] = 2, -1
        before = {name: array.tobytes() for name, array in parameters.items()}
        logits = project_salience_heads(parameters, hidden, topology, extents, array_api=np)
        np.testing.assert_array_equal(logits.impact, [[[1, 4, 7, 10, 13], [0, 1, 2, 3, 4]]])
        np.testing.assert_array_equal(logits.exigency, [[[2, 7, 12, 17, 22], [0, 1, 2, 3, 4]]])
        np.testing.assert_array_equal(logits.novelty, [[[3, 10, 17, 24, 31], [0, 1, 2, 3, 4]]])
        self.assertEqual(before, {name: array.tobytes() for name, array in parameters.items()})
        for name in parameters:
            malformed = dict(parameters)
            del malformed[name]
            with self.subTest(missing=name), self.assertRaises(BilqisError):
                project_salience_heads(malformed, hidden, topology, extents, array_api=np)
        with self.assertRaises(BilqisError):
            project_salience_heads(parameters, hidden.astype(np.float64), topology, extents, array_api=np)
        for name, value in parameters.items():
            for bad in (value.astype(np.float64), np.zeros((6, 768), dtype=np.float32)):
                malformed = {**parameters, name: bad}
                with self.subTest(tensor=name), self.assertRaises(BilqisError):
                    project_salience_heads(malformed, hidden, topology, extents, array_api=np)
        flat = project_salience_heads(parameters, hidden[0, 0], topology, extents, array_api=np)
        self.assertEqual(tuple(flat.impact.shape), (5,))

    def test_literal_rule_boundaries_required_facts_and_policy_rejection(self):
        policy = _policy()
        for value, expected in enumerate(Ordinal):
            self.assertEqual(_derive((_fact(Metric.DECLARED_IMPACT, value, policy),), policy)
                             .impact.ordinal, expected)
        count_cases = ((0, Ordinal.LOW), (1, Ordinal.MODERATE), (2, Ordinal.MODERATE),
                       (3, Ordinal.HIGH), (4, Ordinal.HIGH), (7, Ordinal.HIGH),
                       (8, Ordinal.CRITICAL), (9, Ordinal.CRITICAL))
        for metric in (Metric.DOWNSTREAM_COUNT, Metric.COVERAGE_COUNT,
                       Metric.BLOCKED_COUNT, Metric.REPAIR_COUNT):
            for value, expected in count_cases:
                facts = [_fact(metric, value, policy)]
                if metric.signal is Signal.IMPACT:
                    facts.append(_fact(Metric.DECLARED_IMPACT, 1, policy))
                elif metric is not Metric.BLOCKED_COUNT:
                    facts.append(_fact(Metric.BLOCKED_COUNT, 0, policy))
                actual = _derive(tuple(facts), policy)
                evidence = actual.impact if metric.signal is Signal.IMPACT else actual.exigency
                self.assertEqual(evidence.ordinal, expected, (metric, value))
        deadline_cases = ((0, Ordinal.CRITICAL), (1, Ordinal.HIGH), (2, Ordinal.HIGH),
                          (60, Ordinal.HIGH), (61, Ordinal.MODERATE), (62, Ordinal.MODERATE),
                          (3600, Ordinal.MODERATE), (3601, Ordinal.LOW), (3602, Ordinal.LOW))
        for distance, expected in deadline_cases:
            actual = _derive((_fact(Metric.BLOCKED_COUNT, 0, policy),
                              _fact(Metric.DEADLINE_AT, 100 + distance, policy)), policy)
            self.assertEqual(actual.exigency.ordinal, expected)
        partial = _derive((_fact(Metric.DOWNSTREAM_COUNT, 8, policy),), policy)
        self.assertIsNone(partial.impact.supervised_label)
        self.assertEqual(partial.impact.reason, "MISSING_REQUIRED_FACTS")
        unsupported = _signed(replace(policy, numeric_rules=tuple(
            rule for rule in policy.numeric_rules if rule.metric is not Metric.BLOCKED_COUNT)))
        self.assertEqual(_derive((_fact(Metric.BLOCKED_COUNT, 3, unsupported),), unsupported)
                         .exigency.reason, "UNSUPPORTED_REQUIRED_EVIDENCE")
        with self.assertRaises(BilqisError):
            replace(policy.numeric_rules[0], cut_points=(1, 1, 3, 4))
        with self.assertRaises(BilqisError):
            replace(policy.numeric_rules[0], units="minutes")
        with self.assertRaises(BilqisError):
            replace(policy, numeric_rules=policy.numeric_rules + (policy.numeric_rules[0],))
        with self.assertRaises(BilqisError):
            _derive((_fact(Metric.DECLARED_IMPACT, 4, policy),
                     _fact(Metric.IMPACT_UNKNOWN, 0, policy)), policy)

    def test_comparable_novelty_and_causal_visibility(self):
        policy = _policy()
        for changes, expected in (
                ({}, Ordinal.LOW),
                ({"observed_structure_sha256": "3" * 64}, Ordinal.MODERATE),
                ({"observed_outcome_sha256": "3" * 64}, Ordinal.HIGH),
                ({"observed_structure_sha256": "3" * 64,
                  "observed_outcome_sha256": "4" * 64}, Ordinal.HIGH)):
            comparison = replace(_novelty(), **changes)
            actual = _derive((_fact(Metric.NOVELTY_COMPARISON, comparison, policy),), policy)
            self.assertEqual(actual.novelty.ordinal, expected)
        absent = replace(_novelty(), state=ObservationState.NOT_REPORTED, observed_event_id=None,
                         observed_structure_sha256=None, observed_outcome_sha256=None)
        actual = _derive((_fact(Metric.NOVELTY_COMPARISON, absent, policy),), policy)
        self.assertIsNone(actual.novelty.supervised_label)
        self.assertEqual(actual.basis.facts[0].value.state, ObservationState.NOT_REPORTED)
        with self.assertRaises(BilqisError):
            _derive((_fact(Metric.NOVELTY_COMPARISON, replace(_novelty(), established_at=60), policy),), policy)
        with self.assertRaises(BilqisError):
            _derive((_fact(Metric.NOVELTY_COMPARISON,
                            _novelty(ObservationState.EXPECTED_MISSING), policy),), policy)
        valid = _fact(Metric.BLOCKED_COUNT, 1, policy)
        with self.assertRaises(BilqisError):
            _derive((_signed(replace(valid, effective_time=101)),), policy)
        with self.assertRaises(BilqisError):
            _derive((valid, valid), policy)
        with self.assertRaises(BilqisError):
            _derive((_signed(replace(valid, policy_digest="1" * 64)),), policy)

    def test_dispatch_tiers_holds_age_and_stable_id_are_not_weighted_scores(self):
        policy = _policy()
        fair = _derive((), policy)
        urgent = _derive((_fact(Metric.BLOCKED_COUNT, 3, policy),), policy)
        novel = _derive((_fact(Metric.NOVELTY_COMPARISON,
                               replace(_novelty(), observed_outcome_sha256="4" * 64), policy),), policy)
        options = (
            _option("fair-b", fair, age=10), _option("fair-a", fair, age=10),
            _option("new-fair", fair, age=11),
            _option("novel", novel, action=ActionKind.EXPLORATION, exploration=True),
            _option("unlock", fair, unlocks=1),
            _option("urgent", urgent, relevant=True),
            _option("correction", fair, action=ActionKind.CORRECTION, correction=True,
                    admissible=False, rights=False, ready=False),
            _option("held", urgent, rights=False, relevant=True),
            _option("unadmitted-exploration", novel, action=ActionKind.EXPLORATION))
        evidence = {option.stable_id: (urgent if option.stable_id in ("urgent", "held")
                                      else novel if option.action_kind is ActionKind.EXPLORATION else fair)
                    for option in options}
        ranked = rank_attention_options(options, evidence, fair.basis.snapshot)
        self.assertEqual(tuple(option.stable_id for option in ranked.ordered),
                         ("correction", "urgent", "unlock", "novel", "fair-a", "fair-b", "new-fair"))
        self.assertEqual(tuple(name for name, _ in ranked.held), ("held", "unadmitted-exploration"))
        self.assertEqual(ranked.ordered[0].action_kind, ActionKind.CORRECTION)
        self.assertFalse(ranked.ordered[0].rights_eligible)
        with self.assertRaises(BilqisError):
            rank_attention_options((replace(options[0], downstream_unlocks=99),),
                                   {"fair-b": fair}, fair.basis.snapshot)

    def test_missing_and_explicit_unknown_remain_distinct(self):
        policy = _policy()
        missing = _derive((), policy)
        self.assertEqual(missing.impact.ordinal, Ordinal.UNKNOWN)
        self.assertIsNone(missing.impact.supervised_label)
        explicit = _derive((_fact(Metric.IMPACT_UNKNOWN, 0, policy),), policy)
        self.assertEqual(explicit.impact.ordinal, Ordinal.UNKNOWN)
        self.assertEqual(explicit.impact.supervised_label, 0)
        observed_zero = _derive((_fact(Metric.BLOCKED_COUNT, 0, policy),), policy)
        self.assertEqual(observed_zero.exigency.ordinal, Ordinal.LOW)
        self.assertEqual(observed_zero.exigency.supervised_label, 1)

    def test_source_family_authority_and_label_renaming_boundaries(self):
        policy = _policy()
        missing_family = _signed(replace(policy, source_family_ids=("another-family",)))
        result = _derive((_fact(Metric.DECLARED_IMPACT, 4, missing_family),), missing_family)
        self.assertEqual(result.impact.reason, "UNSUPPORTED_SOURCE_FAMILY")
        self.assertIsNone(result.impact.supervised_label)
        restricted = SourceAuthorityRegistry((replace(_REGISTRY.keys[0], allowed_scopes=(
            SourceAuthorityScope(DependencyKind.POLICY, "salience-policy:"),)),))
        with self.assertRaises(BilqisError):
            verify_salience_inputs((_fact(Metric.DECLARED_IMPACT, 4, policy),), policy,
                                   AuthoritySnapshot((_CONTEXT,), 100, restricted), _CONTEXT)
        renamed_orders = []
        for label in ("B", "C"):
            context = replace(_CONTEXT, scope="grade:" + label)
            facts = (_fact(Metric.BLOCKED_COUNT, 3, policy, context=context),)
            evidence = _derive(facts, policy, context)
            choices = (_option("later", evidence, relevant=True, age=20),
                       _option("earlier", evidence, relevant=True, age=10))
            ranked = rank_attention_options(choices, {choice.stable_id: evidence for choice in choices},
                                            evidence.basis.snapshot)
            renamed_orders.append(tuple(choice.stable_id for choice in ranked.ordered))
        self.assertEqual(renamed_orders, [("earlier", "later"), ("earlier", "later")])
        for context in (replace(_CONTEXT, rights_epoch=2), replace(_CONTEXT, scope="foreign"),
                        replace(_CONTEXT, capability_epoch="9" * 64)):
            with self.assertRaises(BilqisError):
                verify_salience_inputs((_fact(Metric.BLOCKED_COUNT, 3, policy, context=context),),
                                       policy, AuthoritySnapshot((_CONTEXT,), 100, _REGISTRY), context)

    def test_negative_report_without_expectation_basis_is_unlabelled(self):
        policy = _policy()
        negative = replace(_novelty(ObservationState.REPORTED_NEGATIVE),
                           expected_structure_sha256=None, expected_outcome_sha256=None)
        evidence = _derive((_fact(Metric.NOVELTY_COMPARISON, negative, policy),), policy)
        self.assertEqual(evidence.novelty.ordinal, Ordinal.UNKNOWN)
        self.assertIsNone(evidence.novelty.supervised_label)
        self.assertEqual(evidence.basis.facts[0].value.state, ObservationState.REPORTED_NEGATIVE)

    def test_closed_outcome_only_expectation_is_a_comparable_missing_report(self):
        policy = _policy()
        missing = replace(_novelty(ObservationState.EXPECTED_MISSING), expected_structure_sha256=None)
        evidence = _derive((_fact(Metric.NOVELTY_COMPARISON, missing, policy, observed_at=80),), policy)
        self.assertEqual(evidence.novelty.ordinal, Ordinal.CRITICAL)
        self.assertEqual(evidence.novelty.supervised_label, 4)
        with self.assertRaises(BilqisError):
            _derive((_fact(Metric.NOVELTY_COMPARISON, missing, policy, observed_at=79),), policy)
        neither = replace(missing, expected_outcome_sha256=None)
        with self.assertRaises(BilqisError):
            _derive((_fact(Metric.NOVELTY_COMPARISON, neither, policy, observed_at=90),), policy)

    def test_signed_metric_rules_and_expectation_comparison(self):
        policy = _policy()
        facts = (_fact(Metric.DECLARED_IMPACT, 2, policy),
                 _fact(Metric.BLOCKED_COUNT, 3, policy),
                 _fact(Metric.NOVELTY_COMPARISON, _novelty(), policy))
        evidence = _derive(facts, policy)
        self.assertEqual((evidence.impact.ordinal, evidence.exigency.ordinal, evidence.novelty.ordinal),
                         (Ordinal.MODERATE, Ordinal.HIGH, Ordinal.LOW))
        with self.assertRaises(BilqisError):
            _derive((replace(facts[0], value=4),), policy)
        with self.assertRaises(BilqisError):
            _derive((replace(facts[0], context=replace(_CONTEXT, capability_epoch="9" * 64)),), policy)
        missing = _derive((_fact(Metric.NOVELTY_COMPARISON, _novelty(ObservationState.EXPECTED_MISSING),
                                 policy, observed_at=90),), policy)
        negative = _derive((_fact(Metric.NOVELTY_COMPARISON, _novelty(ObservationState.REPORTED_NEGATIVE),
                                  policy),), policy)
        self.assertEqual(missing.novelty.ordinal, Ordinal.CRITICAL)
        self.assertEqual(negative.novelty.ordinal, Ordinal.LOW)
