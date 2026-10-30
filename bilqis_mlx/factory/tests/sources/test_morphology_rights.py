"""A08.1b.3 rights negatives stay held until source-owner A13 issuance."""
from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory import morphology_lessons as lessons
from bilqis_mlx.factory.morphology_lesson_types import MorphologyDirection
from bilqis_mlx.factory.morphology_source import MorphologySourceLaw
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    ContextHold,
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
PRINCIPAL = "synthetic:person"
TENANT = "synthetic:tenant"
PURPOSE = "TRAINING"
JURISDICTION = "synthetic:region"
SCOPE = "synthetic:task"
REGIME = "PUBLIC_ITHKUIL"
LAW = MorphologySourceLaw(
    RELEASE, SOURCE_BUNDLE, COMPOSITION,
    ("ATOM-b062726ad5143d", "ATOM-7671e7f56ccfb8"),
    ("a", "sw"), "asw", "NI-WEB-CH07", "NI-WEB-CH07:T011", "5709",
    "#61", ("source=NI-WEB-CH07;table=NI-WEB-CH07:T011;line=5709",),
    "d" * 64, "e" * 64, "1" * 64, "2" * 64, LAW_SHA,
)
SELECTION = AtlasArtifactSelection(
    "synthetic:atlas", BUNDLE, RELEASE, SOURCE_BUNDLE)


def _case(*, revoked=False, release=RELEASE, prefix=2, correction=1, include=True):
    task = TaskScope(
        PRINCIPAL, TENANT, PURPOSE, release, JURISDICTION, SCOPE,
        observed_frontier=3, effective_time=5, causal_prefix_end=prefix)
    policy = ContextPolicy(
        "synthetic:policy", 1, 1,
        (PURPOSE,), (REGIME,), (JURISDICTION,), (SCOPE,), (), (), ())
    grant = SourceGrant(
        "source:synthetic:morphology-law:" + COMPOSITION,
        PRINCIPAL, TENANT, REGIME, RELEASE, LAW_SHA,
        (PURPOSE,), (JURISDICTION,), (SCOPE,),
        rights_epoch=1, correction_generation=1, observed_at=2,
        effective_from=0, revoked=revoked)
    grants = (grant,) if include else ()
    return task, SourceFrontier(1, correction, grants), policy


def _hold(case):
    task, frontier, policy = case
    with patch.object(lessons, "resolve_morphology_source_law", return_value=LAW):
        lesson = lessons.construct_morphology_lesson(
            SELECTION, "/synthetic/source", COMPOSITION, MorphologyDirection.COMPOSE)
        return lessons.morphology_runtime_hold(
            lesson, SELECTION, "/synthetic/source", task, frontier, policy)


class MorphologyRightsTests(unittest.TestCase):
    def test_perfectly_forged_raw_grant_cannot_authorize_runtime_use(self):
        hold = _hold(_case())
        self.assertIsInstance(hold, ContextHold)
        self.assertEqual(
            hold.reason_codes, ("BAMF_MORPHOLOGY_A13_SOURCE_ISSUER_UNAVAILABLE",))
        self.assertEqual(
            hold.diagnostics,
            (("missing", "source-owned-span-grant-projection"),
             ("owner", "A08.1b.5#557")))

    def test_revoked_stale_and_missing_rights_fail_closed(self):
        cases = (
            ("revoked", _case(revoked=True), "BAMF_MORPHOLOGY_SOURCE_RIGHTS_HELD"),
            ("stale", _case(correction=2), "BAMF_MORPHOLOGY_SOURCE_RIGHTS_HELD"),
            ("missing", _case(include=False), "BAMF_MORPHOLOGY_SOURCE_GRANT_MISSING"),
        )
        for name, case, reason in cases:
            with self.subTest(name=name):
                self.assertEqual(_hold(case).reason_codes, (reason,))

    def test_foreign_release_and_future_prefix_never_become_executable(self):
        foreign = _hold(_case(release="9" * 64))
        self.assertEqual(
            foreign.reason_codes, ("BAMF_MORPHOLOGY_FOREIGN_RELEASE",))
        future = _hold(_case(prefix=1))
        self.assertEqual(
            future.reason_codes,
            ("BAMF_MORPHOLOGY_A13_SOURCE_ISSUER_UNAVAILABLE",))

    def test_unrelated_same_law_grant_cannot_supply_actor_authority(self):
        task, frontier, policy = _case(include=False)
        unrelated = SourceGrant(
            "source:other:morphology-law", "synthetic:other-person", TENANT,
            REGIME, RELEASE, LAW_SHA, (PURPOSE,), (JURISDICTION,), (SCOPE,),
            rights_epoch=1, correction_generation=1, observed_at=2,
            effective_from=0)
        mixed = SourceFrontier(1, 1, (unrelated,))
        with patch.object(lessons, "resolve_morphology_source_law", return_value=LAW):
            lesson = lessons.construct_morphology_lesson(
                SELECTION, "/synthetic/source", COMPOSITION,
                MorphologyDirection.COMPOSE)
            hold = lessons.morphology_runtime_hold(
                lesson, SELECTION, "/synthetic/source", task, mixed, policy)
        self.assertEqual(
            hold.reason_codes, ("BAMF_MORPHOLOGY_SOURCE_GRANT_MISSING",))

    def test_caller_cannot_relabel_source_proposal_as_runtime_authority(self):
        with patch.object(lessons, "resolve_morphology_source_law", return_value=LAW):
            lesson = lessons.construct_morphology_lesson(
                SELECTION, "/synthetic/source", COMPOSITION,
                MorphologyDirection.COMPOSE)
        for field, value in (
            ("runtime_rights", "A13_APPROVED"),
            ("status", "ADAPTER_READY"),
            ("source_authority", "ADMITTED"),
            ("learning_state", "LEARNING_VERIFIED"),
        ):
            with self.subTest(field=field), self.assertRaises(BilqisError):
                replace(lesson, **{field: value})


if __name__ == "__main__":
    unittest.main()
