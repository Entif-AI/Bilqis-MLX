"""A08.1b.3 source-valid morphology proposals and independent checking."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory import morphology_lessons as lessons
from bilqis_mlx.factory.morphology_lesson_types import (
    MorphologyAnswer,
    MorphologyDirection,
)
from bilqis_mlx.factory.morphology_source import MorphologySourceLaw
from bilqis_mlx.semantics.atlas_projection import (
    FormalDomainBinding,
    compile_atlas_release,
    persist_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    ContextPolicy,
    SourceFrontier,
    SourceGrant,
    TaskScope,
)


RELEASE = "a" * 64
BUNDLE = "b" * 64
SOURCE_BUNDLE = "c" * 64
LAW_SHA = "f" * 64
COMPOSITION = "COMP-00a9e6c3998d74"
REAL_COMPOSITION = "COMP-1a7a421841756f"
LAW = MorphologySourceLaw(
    RELEASE, SOURCE_BUNDLE, COMPOSITION,
    ("ATOM-b062726ad5143d", "ATOM-7671e7f56ccfb8"),
    ("a", "sw"), "asw", "NI-WEB-CH07", "NI-WEB-CH07:T011", "5709",
    "#61", ("source=NI-WEB-CH07;table=NI-WEB-CH07:T011;line=5709",),
    "d" * 64, "e" * 64, "1" * 64, "2" * 64, LAW_SHA,
)
SELECTION = AtlasArtifactSelection(
    "synthetic:atlas", BUNDLE, RELEASE, SOURCE_BUNDLE)


def _construct(direction: MorphologyDirection):
    with patch.object(lessons, "resolve_morphology_source_law", return_value=LAW):
        return lessons.construct_morphology_lesson(
            SELECTION, "/synthetic/source", COMPOSITION, direction)


class MorphologyLessonTests(unittest.TestCase):
    def test_compose_and_decompose_are_inverse_source_valid_programs(self):
        compose = _construct(MorphologyDirection.COMPOSE)
        self.assertEqual(compose.positive.inputs, ("a", "sw"))
        self.assertEqual(compose.positive.answer.value, "asw")
        self.assertEqual(
            compose.source_valid_contrast.direction, MorphologyDirection.DECOMPOSE)
        self.assertEqual(compose.source_valid_contrast.answer.value, ("a", "sw"))
        self.assertEqual(compose.constituents, LAW.component_ids)
        self.assertEqual(compose.prerequisite_closure, LAW.component_ids)
        self.assertEqual(compose.status, "SOURCE_VALID_NOT_ADMITTED")
        self.assertEqual(compose.runtime_rights, "A13_RIGHTS_UNVERIFIED")
        self.assertEqual(compose.learning_state, "LEARNING_UNVERIFIED")
        decompose = _construct(MorphologyDirection.DECOMPOSE)
        self.assertEqual(decompose.positive.inputs, ("asw",))
        self.assertEqual(decompose.positive.answer.value, ("a", "sw"))
        self.assertEqual(
            decompose.source_valid_contrast.direction, MorphologyDirection.COMPOSE)

    def test_checker_replays_source_without_generator_helpers(self):
        lesson = _construct(MorphologyDirection.COMPOSE)
        with (patch.object(lessons, "construct_morphology_lesson",
                           side_effect=AssertionError("generator consulted")),
              patch.object(lessons, "_facts",
                           side_effect=AssertionError("generator facts consulted")),
              patch.object(lessons, "resolve_morphology_source_law", return_value=LAW)):
            self.assertTrue(lessons.check_morphology_lesson(
                lesson, lesson.positive.answer, SELECTION, "/synthetic/source"))
            wrong = MorphologyAnswer(RELEASE, "MORPHOLOGY_SURFACE", "swa")
            self.assertFalse(lessons.check_morphology_lesson(
                lesson, wrong, SELECTION, "/synthetic/source"))

    def test_forged_authority_or_learning_status_is_rejected(self):
        lesson = _construct(MorphologyDirection.COMPOSE)
        for change in (
            {"status": "ADAPTER_READY"},
            {"source_authority": "ADMITTED"},
            {"runtime_rights": "A13_APPROVED"},
            {"learning_state": "LEARNING_VERIFIED"},
        ):
            with self.subTest(change=change), self.assertRaises(BilqisError):
                replace(lesson, **change)
        object.__setattr__(lesson, "source_law_sha256", "0" * 64)
        with (patch.object(lessons, "resolve_morphology_source_law", return_value=LAW),
              self.assertRaises(BilqisError) as caught):
            lessons.check_morphology_lesson(
                lesson, lesson.positive.answer, SELECTION, "/synthetic/source")
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_MORPHOLOGY_LESSON_SOURCE_EVIDENCE_MISMATCH")

    def test_source_held_law_never_becomes_a_lesson(self):
        def held(*_args, **_kwargs):
            lessons._fail("BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
        with (patch.object(lessons, "resolve_morphology_source_law", side_effect=held),
              self.assertRaises(BilqisError) as caught):
            lessons.construct_morphology_lesson(
                SELECTION, "/synthetic/source", "COMP-0060583f4d9807",
                MorphologyDirection.COMPOSE)
        self.assertEqual(
            caught.exception.context["reason"], "BAMF_MORPHOLOGY_SOURCE_LAW_HELD")

    def test_real_a01_law_roundtrips_source_only_if_supplied(self):
        corpus = os.environ.get("BILQIS_ATLAS_REAL_CORPUS")
        if not corpus:
            self.skipTest("real pinned A01 corpus not supplied")
        root = Path(__file__).resolve().parents[4]
        prior = root / "bilqis_mlx/semantics/copular_registry_v1.json"
        boolean = root / "bilqis_mlx/semantics/legacy_abi_v1.json"
        numeric = root / "bilqis_mlx/semantics/numeric_v1.json"
        bindings = (
            FormalDomainBinding(
                "boolean", "bilqis_mlx/semantics/legacy_abi_v1.json",
                hashlib.sha256(boolean.read_bytes()).hexdigest(),
                ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
                ("B.NOT", "B.AND")),
            FormalDomainBinding(
                "numeric", "bilqis_mlx/semantics/numeric_v1.json",
                hashlib.sha256(numeric.read_bytes()).hexdigest(),
                ("bilqis.numeric/v1:school.op.COUNT",
                 "bilqis.numeric/v1:school.op.SUCC"),
                ("C.COUNT", "C.SUCCESSOR")),
        )
        release = compile_atlas_release(
            corpus, Path(corpus) / "coverage.json", prior, bindings)
        with tempfile.TemporaryDirectory() as directory:
            artifact = persist_atlas_release(release, directory)
            selection = AtlasArtifactSelection(
                artifact.path, artifact.bundle_id, release.digest,
                release.source_bundle_id)
            lesson = lessons.construct_morphology_lesson(
                selection, corpus, REAL_COMPOSITION, MorphologyDirection.COMPOSE)
            self.assertEqual(lesson.positive.answer.value, "eabẓ")
            self.assertTrue(lessons.check_morphology_lesson(
                lesson, lesson.positive.answer, selection, corpus))
            law = lessons.resolve_morphology_source_law(
                selection, corpus, REAL_COMPOSITION)
            task = TaskScope(
                "synthetic:person", "synthetic:tenant", "TRAINING",
                law.semantic_release, "synthetic:region", "synthetic:task",
                observed_frontier=3, effective_time=5, causal_prefix_end=2)
            policy = ContextPolicy(
                "synthetic:policy", 1, 1, ("TRAINING",), ("PUBLIC_ITHKUIL",),
                ("synthetic:region",), ("synthetic:task",), (), (), ())
            forged = SourceGrant(
                "source:forged:morphology-law", task.principal_id, task.tenant_id,
                "PUBLIC_ITHKUIL", law.semantic_release, law.law_sha256,
                (task.purpose,), (task.jurisdiction,), (task.scope,),
                rights_epoch=1, correction_generation=1, observed_at=2,
                effective_from=0)
            hold = lessons.morphology_runtime_hold(
                lesson, selection, corpus, task, SourceFrontier(1, 1, (forged,)),
                policy)
            self.assertEqual(
                hold.reason_codes,
                ("BAMF_MORPHOLOGY_A13_SOURCE_ISSUER_UNAVAILABLE",))


if __name__ == "__main__":
    unittest.main()
