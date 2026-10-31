"""Actual pinned A01 source rows must enter the public A13 context boundary."""
from dataclasses import replace
from unittest import TestCase, skipUnless

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.skos_curriculum.checkers import compile_source_constructive_lessons
from bilqis_mlx.factory.skos_curriculum.source_context import (
    issue_source_lesson_contexts, project_source_lesson_contexts,
)
from bilqis_mlx.factory.skos_curriculum.programs.tests.real_fixtures import ARTIFACT, selection
from bilqis_mlx.factory.tests.skos.test_source_context import _task, _policy
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextHold, SourceFrontier,
)


@skipUnless(ARTIFACT, "real pinned A01 artifact not mounted")
class RealSourceLessonContextTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas = selection()
        cls.lessons = compile_source_constructive_lessons(cls.atlas)
        cls.lesson = next(lesson for lesson in cls.lessons.lessons
                          if lesson.family_id == "positive_identity"
                          and lesson.positive_fact[2].startswith("atomic/")
                          and lesson.contrast_fact[2].startswith("atomic/"))
        cls.task = replace(_task(), semantic_release=cls.atlas.release_sha256)
        cls.policy = _policy()
        cls.contexts, cls.frontier = issue_source_lesson_contexts(
            cls.lesson, cls.lessons, cls.atlas, cls.task, cls.policy, SourceFrontier(2, 3, ()))

    def test_pinned_source_rows_project_both_positive_and_contrast(self):
        result = project_source_lesson_contexts(self.contexts, self.task, self.frontier, self.policy)
        self.assertIsInstance(result, ApprovedContextProjection)
        self.assertEqual(len(result.attention_handles), 2)
        self.assertEqual(self.contexts.learning_state, "LEARNING_UNVERIFIED")

    def test_contrast_only_revocation_blocks_projection_and_reissuance(self):
        handle = self.contexts.contrast.envelope.members[0].source_handle
        revoked = replace(self.frontier, grants=tuple(
            replace(grant, revoked=True) if grant.source_handle == handle else grant
            for grant in self.frontier.grants))
        held = project_source_lesson_contexts(self.contexts, self.task, revoked, self.policy)
        self.assertIsInstance(held, ContextHold)
        self.assertIn(handle, held.source_handles)
        with self.assertRaises(BilqisError):
            issue_source_lesson_contexts(
                self.lesson, self.lessons, self.atlas, self.task, self.policy, revoked)
