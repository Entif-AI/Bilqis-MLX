"""Frozen original bytes and explicitly non-learning rubric translations."""
from dataclasses import replace
import unittest
import hashlib
import json

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.capability_evidence_history import (
    FrozenHistory, TranslatorSpec, freeze_assessment, translate_history,
)
from bilqis_mlx.runtime.capability_retention import AssessmentPair, retain_candidate
from bilqis_mlx.runtime.tests.test_bamf_capability_retention import _evidence, PARENT, CANDIDATE


class CapabilityHistoryTests(unittest.TestCase):
    def test_translation_preserves_original_bytes_and_cannot_claim_learning(self):
        evidence = _evidence()
        assessment = evidence.target.parent
        frozen = freeze_assessment(assessment)
        original = frozen.payload
        cold = FrozenHistory(frozen.payload, frozen.sha256)
        self.assertEqual(cold.payload, original)
        record = frozen.record()
        spec = TranslatorSpec(
            "fixture-translator", "v1", "1" * 64,
            record["rubric_sha256"], "2" * 64,
            record["policy_sha256"], "3" * 64,
            record["scope_sha256"], "4" * 64,
            tuple(record["source_family_ids"]), ("normalized-family",),
            ("target",), "Different rubric; retrospective comparison only.")
        translated = translate_history(frozen, spec, lambda history: (("target", 3, 3),))
        self.assertEqual(record["scores"], [["target", 0, 3]])
        self.assertEqual(translated.scores, (("target", 3, 3),))
        self.assertEqual(translated.source_history_sha256, frozen.sha256)
        self.assertFalse(translated.fresh_learning)
        self.assertEqual(frozen.payload, original)
        with self.assertRaises(BilqisError):
            AssessmentPair(assessment, translated)
        with self.assertRaises(BilqisError):
            retain_candidate(PARENT, CANDIDATE, translated)
        with self.assertRaises(BilqisError):
            FrozenHistory(original + b" ", frozen.sha256)
        with self.assertRaisesRegex((TypeError, ValueError), r"fresh_learning.*init=False"):
            replace(translated, fresh_learning=True)

    def test_rehashed_malformed_replay_and_noncanonical_bytes_fail_closed(self):
        frozen = freeze_assessment(_evidence().target.parent)
        mutations = (
            lambda record: record.update(replay_records=[None], solver_contracts=[]),
            lambda record: record["replay_records"][0].update(generation_digest="9" * 64),
            lambda record: record.update(replay_records=record["replay_records"][:1],
                                         solver_contracts=record["solver_contracts"][:1]),
            lambda record: record["replay_records"][0]["costs"].update(pure_operations=9),
            lambda record: record["replay_records"][0].update(schema_version="unsupported/v0"),
            lambda record: record["replay_records"][0].update(raw_answer="must not be replay metadata"),
        )
        for mutate in mutations:
            record = frozen.record()
            mutate(record)
            payload = json.dumps(record, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode()
            with self.subTest(mutation=mutate), self.assertRaises(BilqisError):
                FrozenHistory(payload, hashlib.sha256(payload).hexdigest())
        pretty = json.dumps(frozen.record(), indent=2).encode()
        with self.assertRaises(BilqisError):
            FrozenHistory(pretty, hashlib.sha256(pretty).hexdigest())

    def test_foreign_source_or_invalid_destination_translation_fails_closed(self):
        frozen = freeze_assessment(_evidence().target.parent)
        record = frozen.record()
        spec = TranslatorSpec(
            "fixture-translator", "v1", "1" * 64,
            record["rubric_sha256"], "2" * 64,
            record["policy_sha256"], "3" * 64,
            record["scope_sha256"], "4" * 64,
            tuple(record["source_family_ids"]), ("normalized-family",),
            ("target",), "Scope differs.")
        with self.assertRaises(BilqisError):
            translate_history(frozen, replace(spec, source_rubric_sha256="9" * 64),
                              lambda history: (("target", 3, 3),))
        for scores in ((), (("foreign", 1, 1),), (("target", 4, 3),),
                       (("target", True, 3),), (("target", 1, 3), ("target", 1, 3))):
            with self.subTest(scores=scores), self.assertRaises(BilqisError):
                translate_history(frozen, spec, lambda history: scores)
        def malformed(history):
            raise ValueError("malformed translated score")
        with self.assertRaises(BilqisError):
            translate_history(frozen, spec, malformed)
