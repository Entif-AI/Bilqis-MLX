from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.skos_curriculum.source_context import (
    SourceLessonContexts, _merge_issued_grants, _source_fact_context,
    project_source_lesson_contexts,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ApprovedContextProjection, ContextHold, ContextPolicy,
    SourceFrontier, TaskScope,
)


RELEASE = "a" * 64
SOURCE_BUNDLE = "b" * 64


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
    concept = SimpleNamespace(semantic_id=semantic_id, source_refs=(ref,))
    return SimpleNamespace(
        concepts=(SimpleNamespace(concept=concept),),
        source_bundle_id=SOURCE_BUNDLE,
    )


def _context(semantic_id, key, task, policy):
    with patch(
        "bilqis_mlx.factory.skos_curriculum.source_context.load_pinned_atlas_snapshot",
        return_value=_snapshot(semantic_id, "source", "source_sections", key),
    ):
        return _source_fact_context(
            ("identity", semantic_id, f"source/source_sections/{key}"),
            SimpleNamespace(), task, policy,
            rights_epoch=2, correction_generation=3)


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

        contrast_handle = contrast.envelope.members[0].source_handle
        revoked = tuple(replace(item, revoked=True)
                        if item.source_handle == contrast_handle else item
                        for item in grants)
        held = project_source_lesson_contexts(
            contexts, task, SourceFrontier(2, 3, revoked), policy)
        self.assertIsInstance(held, ContextHold)
        self.assertIn(contrast_handle, held.source_handles)

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
                    SimpleNamespace(), task, policy,
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
                    fact, SimpleNamespace(), task, policy,
                    rights_epoch=2, correction_generation=3)


if __name__ == "__main__":
    unittest.main()
