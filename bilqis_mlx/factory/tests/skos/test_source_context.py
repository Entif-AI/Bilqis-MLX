from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.skos_curriculum.source_context import (
    SourceLessonContexts, _merge_issued_grants, _source_fact_context,
    project_source_lesson_contexts, source_lesson_expiry_task,
)
from bilqis_mlx.factory.skos_curriculum.source_context_policy import (
    SourceContextTransitionAuthority, issue_source_context_transition_authority,
)
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ApprovedContextProjection, ContextHold, ContextPolicy,
    SourceFrontier, TaskScope, transition_context,
)


RELEASE = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
SOURCE_BUNDLE = "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec"
ATLAS_BUNDLE = "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
SELECTION = AtlasArtifactSelection(
    "/fixture/a01-atlas.json", ATLAS_BUNDLE, RELEASE, SOURCE_BUNDLE)


def _task(prefix=8):
    return TaskScope(
        "fixture:person", "fixture:tenant", "TRAINING", RELEASE,
        "fixture:region", "fixture:scope", 9, 9, prefix)


def _policy():
    return ContextPolicy(
        "fixture:policy", 1, 2,
        ("TRAINING",), (PUBLIC_FORMAL,), ("fixture:region",),
        ("fixture:scope",), (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),), ())


def _snapshot(semantic_id, domain, table, key):
    ref = SimpleNamespace(domain=domain, table=table, key=key)
    concept = SimpleNamespace(semantic_id=semantic_id, source_rows=(ref,))
    return SimpleNamespace(
        concepts=(SimpleNamespace(concept=concept),),
        source_bundle_id=SOURCE_BUNDLE,
    )


def _context(semantic_id, key, task, policy, *, authority=None):
    with patch(
        "bilqis_mlx.factory.skos_curriculum.source_context.load_pinned_atlas_snapshot",
        return_value=_snapshot(semantic_id, "source", "source_sections", key),
    ):
        return _source_fact_context(
            ("identity", semantic_id, f"source/source_sections/{key}"),
            SELECTION, task, policy,
            rights_epoch=policy.rights_epoch,
            correction_generation=(
                3 if authority is None
                else authority.frontier.correction_generation),
            observed_at=(None if authority is None
                         else authority.task.observed_frontier),
            effective_from=(0 if authority is None else authority.effective_from),
            effective_until=(None if authority is None
                             else authority.effective_until))


def _contexts(task, policy, *, authority=None):
    positive = _context(
        "fixture:positive", "NI-WEB-CH01:1.0", task, policy,
        authority=authority)
    contrast = _context(
        "fixture:contrast", "NI-WEB-CH01:1.1", task, policy,
        authority=authority)
    grants = tuple(sorted(
        (*positive.grants, *contrast.grants),
        key=lambda item: item.source_handle))
    return (
        SourceLessonContexts(RELEASE, positive, contrast, grants, authority),
        SourceFrontier(
            policy.rights_epoch,
            (3 if authority is None else authority.frontier.correction_generation),
            grants),
    )


class SourceLessonContextTests(unittest.TestCase):
    def test_positive_and_contrast_need_current_a13_grants(self):
        task, policy = _task(), _policy()
        positive = _context("fixture:positive", "NI-WEB-CH01:1.0", task, policy)
        contrast = _context("fixture:contrast", "NI-WEB-CH01:1.1", task, policy)
        grants = tuple(sorted((*positive.grants, *contrast.grants),
                              key=lambda item: item.source_handle))
        contexts = SourceLessonContexts(RELEASE, positive, contrast, grants)
        projected = project_source_lesson_contexts(
            contexts, task, SourceFrontier(2, 3, grants), policy)
        self.assertIsInstance(projected, ApprovedContextProjection)
        self.assertEqual(len(projected.attention_handles), 2)
        self.assertTrue(all(item.effective_until is None for item in grants))

        contrast_handle = contrast.envelope.members[0].source_handle
        revoked = tuple(replace(item, revoked=True)
                        if item.source_handle == contrast_handle else item
                        for item in grants)
        held = project_source_lesson_contexts(
            contexts, task, SourceFrontier(2, 3, revoked), policy)
        self.assertIsInstance(held, ContextHold)
        self.assertIn(contrast_handle, held.source_handles)

    def test_explicit_policy_window_expires_source_rows_and_emits_invalidation(self):
        authority = issue_source_context_transition_authority(SELECTION)
        task, policy = authority.task, authority.policy
        contexts, frontier = _contexts(task, policy, authority=authority)
        before = project_source_lesson_contexts(
            contexts, task, frontier, policy)
        self.assertIsInstance(before, ApprovedContextProjection)
        self.assertEqual(
            {item.effective_until for item in frontier.grants},
            {authority.effective_until})

        expiry_task = source_lesson_expiry_task(
            contexts, task, frontier, policy)
        held = project_source_lesson_contexts(
            contexts, expiry_task, frontier, policy)
        self.assertIsInstance(held, ContextHold)
        self.assertEqual(
            held.reason_codes, ("BAMF_CONTEXT_TEMPORAL_MISMATCH",))
        transition = transition_context(
            before, (contexts.positive.envelope, contexts.contrast.envelope),
            expiry_task, frontier, policy)
        self.assertEqual(len(transition.invalidations), 1)
        self.assertEqual(
            transition.invalidations[0].old_context_digest, before.digest)

    def test_observation_movement_cannot_fabricate_expiry(self):
        authority = issue_source_context_transition_authority(SELECTION)
        task, policy = authority.task, authority.policy
        contexts, frontier = _contexts(task, policy, authority=authority)
        moved = replace(task, observed_frontier=1000)
        projected = project_source_lesson_contexts(
            contexts, moved, frontier, policy)
        self.assertIsInstance(projected, ApprovedContextProjection)
        self.assertEqual(
            {item.effective_until for item in frontier.grants},
            {authority.effective_until})

    def test_reissuance_cannot_resurrect_revoked_grant(self):
        task, policy = _task(), _policy()
        positive = _context("fixture:positive", "NI-WEB-CH01:1.0", task, policy)
        contrast = _context("fixture:contrast", "NI-WEB-CH01:1.1", task, policy)
        grants = tuple(sorted((*positive.grants, *contrast.grants),
                              key=lambda item: item.source_handle))
        contrast_handle = contrast.envelope.members[0].source_handle
        revoked = tuple(replace(item, revoked=True)
                        if item.source_handle == contrast_handle else item
                        for item in grants)
        with self.assertRaises(Exception):
            _merge_issued_grants(SourceFrontier(2, 3, revoked), grants)

    def test_a01_domain_table_key_must_match_exact_source_fact(self):
        task, policy = _task(), _policy()
        snapshot = _snapshot(
            "fixture:positive", "source", "source_sections", "NI-WEB-CH01:1.0")
        with patch(
            "bilqis_mlx.factory.skos_curriculum.source_context.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            with self.assertRaises(Exception):
                _source_fact_context(
                    ("identity", "fixture:positive",
                     "wrong/source_sections/NI-WEB-CH01:1.0"),
                    SELECTION, task, policy,
                    rights_epoch=2, correction_generation=3)

    def test_source_local_visibility_is_not_csv_file_offset(self):
        task, policy = _task(prefix=1), _policy()
        context = _context(
            "fixture:positive", "NI-WEB-CH01:1.0", task, policy)
        self.assertGreater(context.witness.record_start_byte, 1)
        self.assertEqual(context.envelope.frame.source_span.start, 0)
        self.assertEqual(context.envelope.frame.source_span.end, 1)
        self.assertEqual(context.envelope.members[0].visible_at_prefix, 1)

    def test_abi_or_relation_fact_cannot_mint_source_row_provenance(self):
        task, policy = _task(), _policy()
        for fact in (
            ("identity", "formal:x", "abi:FORMAL_DOMAIN:1"),
            ("relation", "a", "b"),
        ):
            with self.subTest(fact=fact), self.assertRaises(Exception):
                _source_fact_context(
                    fact, SELECTION, task, policy,
                    rights_epoch=2, correction_generation=3)

    def test_policy_window_cannot_be_caller_constructed_or_reused_across_scope(self):
        with self.assertRaises(BilqisError):
            SourceContextTransitionAuthority()
        authority = issue_source_context_transition_authority(SELECTION)
        task, policy = authority.task, authority.policy
        contexts, issued_frontier = _contexts(task, policy, authority=authority)
        moved = replace(task, scope="fixture:other-scope")
        with self.assertRaises(BilqisError):
            source_lesson_expiry_task(
                contexts, moved, issued_frontier, policy)

    def test_caller_selected_effective_time_cannot_mint_invalidation(self):
        authority = issue_source_context_transition_authority(SELECTION)
        task, policy = authority.task, authority.policy
        contexts, frontier = _contexts(task, policy, authority=authority)
        forged = replace(task, effective_time=authority.effective_from)
        self.assertNotEqual(forged, authority.task)
        with self.assertRaises(BilqisError):
            source_lesson_expiry_task(contexts, forged, frontier, policy)

    def test_post_issue_authority_tampering_fails_closed(self):
        authority = issue_source_context_transition_authority(SELECTION)
        object.__setattr__(
            authority, "effective_until", authority.effective_until + 100)
        with self.assertRaises(BilqisError):
            authority.__post_init__()


if __name__ == "__main__":
    unittest.main()
