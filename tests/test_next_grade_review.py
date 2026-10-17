"""Next-grade selection is a repeatable evidence gate, not Sheet scheduling."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.next_grade_review import (QUESTION_IDS, assess, load_review, subject_digest)


def candidate(identifier, *, modality="DIRECT_TEXT_SEMANTIC_TRANSFER"):
    return {
        "id": identifier,
        "source": "repo:source/verified/" + identifier,
        "text_model_relevance": modality,
        "needs_neural_learning": "Independent retained transfer probe, not a codec lookup",
        "smallest_increment": "One independently tested semantic constituent",
        "prerequisites": [{"id": "A.IDENTITY", "state": "MASTERED",
                           "evidence": "run:checkpoint/verified"}],
        "frontloaded_foundations": [],
        "unlocks": [{"capability": "E.COMPOSE", "via": identifier,
                     "why": "Composes learned constituent with an unfamiliar relation"}],
    }


def proposal():
    item = {
        "schema": "bilqis.next-grade-review/v2",
        "authority": "IPR-0220/grade-questions-20261017",
        "grade": "D", "parent_release": "fixed-parent-v1",
        "modality": "TEXT_ONLY",
        "selected": "semantic-binding",
        "candidates": [candidate("semantic-binding"), candidate("phonology")],
        "decision": {
            "why_now": "Binds earlier predicates to new scopes before morphology",
            "why_not_alternatives": {"phonology": "Most legality checks are a codec"},
            "what_changed_since_last_grade": "C retained grounded number operations",
            "expected_near_term_transfer": "Composing predicates in unseen worlds",
            "smallest_staircase_step": "Reuse current types; introduce one binder",
        },
        "semantic_function_families": {
            "association": {"posture": "DEFERRED", "rationale": "No lexical sense retrieval in this grade"},
            "disambiguation": {"posture": "DEFERRED", "rationale": "No context-varying natural language input"},
            "identification": {"posture": "FOUNDATIONAL", "rationale":
                               "Teach positive typed operations from mastered prerequisites"},
        },
        "reviews": {name: {q: {"status": "EVIDENCED", "evidence": [
            "repo:source/qualification/" + name + "/" + q]}
            for q in QUESTION_IDS} for name in ("selection", "construction", "admission")},
    }
    for phase in item["reviews"].values():
        phase["subject_sha256"] = subject_digest(item)
    return item


class NextGradeReviewTests(unittest.TestCase):
    def test_semantic_function_families_are_considered_without_forcing_nlp(self):
        record = proposal()
        self.assertEqual(assess(record, grade="D", parent_release="fixed-parent-v1",
                                phase="admission")["status"], "READY_FOR_INDEPENDENT_REVIEW")
        del record["semantic_function_families"]["association"]
        blockers = assess(record, grade="D", parent_release="fixed-parent-v1")["blockers"]
        self.assertIn("SEMANTIC_FUNCTION_NOT_CONSIDERED:association", blockers)

    def test_required_contextual_function_cannot_self_certify(self):
        record = proposal()
        record["semantic_function_families"]["disambiguation"] = {
            "posture": "REQUIRES_QUALIFIED_IMPLEMENTATION",
            "rationale": "This candidate calls for contextual sense resolution",
            "evidence": "repo:proposed-not-validated",
        }
        blockers = assess(record, grade="D", parent_release="fixed-parent-v1")["blockers"]
        self.assertIn("SEMANTIC_FUNCTION_QUALIFICATION_REQUIRED:disambiguation", blockers)
        record["semantic_function_families"]["association"]["rationale"] = ""
        self.assertIn("SEMANTIC_FUNCTION_RATIONALE_MISSING:association", assess(
            record, grade="D", parent_release="fixed-parent-v1")["blockers"])

    def test_malformed_function_posture_fails_closed(self):
        record = proposal()
        record["semantic_function_families"]["association"]["posture"] = ["invalid"]
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SEMANTIC_FUNCTION_POSTURE_INVALID:association", result["blockers"])

    def test_semantic_function_plan_changes_invalidate_completed_reviews(self):
        record = proposal()
        record["semantic_function_families"]["grounding"] = {
            "posture": "FOUNDATIONAL", "rationale": "Future extension beyond initial three families"
        }
        self.assertIn("REVIEW_SCOPE_STALE:selection", assess(
            record, grade="D", parent_release="fixed-parent-v1")["blockers"])

    def test_malformed_candidate_and_decision_fail_closed(self):
        record = proposal()
        record["candidates"] = [candidate("valid"), {"id": ["unhashable"]}]
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("GRADE_CANDIDATE_IDENTITY_INVALID", result["blockers"])

        record = proposal()
        record["decision"] = ["not a decision object"]
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("GRADE_DECISION_REASON_MISSING:why_now", result["blockers"])

    def test_malformed_selected_source_and_review_hash_fail_closed(self):
        record = proposal()
        record["candidates"][0]["text_model_relevance"] = ["unexpected-list"]
        record["candidates"][0]["source"] = ["not a source reference"]
        record["reviews"]["selection"]["Q01"]["evidence"] = [123]
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SELECTED_TOPIC_SOURCE_NOT_INDEPENDENT", result["blockers"])
        self.assertIn("REVIEW_QUESTION_UNRESOLVED:selection:Q01", result["blockers"])

    def test_all_ten_questions_recur_at_each_phase(self):
        record = proposal()
        result = assess(record, grade="D", parent_release="fixed-parent-v1", phase="admission")
        self.assertEqual(result["status"], "READY_FOR_INDEPENDENT_REVIEW")
        self.assertEqual(result["question_ids"], list(QUESTION_IDS))
        for phase in ("selection", "construction", "admission"):
            assert phase in result["reviewed_phases"]
        del record["reviews"]["construction"]["Q09"]
        result = assess(record, grade="D", parent_release="fixed-parent-v1", phase="admission")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("REVIEW_QUESTION_MISSING:construction:Q09", result["blockers"])

    def test_sheet_topic_cannot_self_select_or_outvote_alternatives(self):
        record = proposal()
        record["selected"] = "phonology"
        record["candidates"][1]["text_model_relevance"] = "UNKNOWN"
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertIn("SELECTED_TOPIC_TEXT_RELEVANCE_UNPROVEN", result["blockers"])
        record["candidates"][1]["text_model_relevance"] = "DETERMINISTIC_CODEC_SUFFICIENT"
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertIn("SELECTED_TOPIC_TEXT_RELEVANCE_UNPROVEN", result["blockers"])
        record["selected"] = None
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertIn("NEXT_GRADE_NOT_SELECTED", result["blockers"])

    def test_unsupported_prerequisite_or_unlinked_unlock_blocks(self):
        record = proposal()
        record["candidates"][0]["prerequisites"] = [
            {"id": "D.BIND", "state": "REQUIRED_NOT_TAUGHT", "evidence": ""}]
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertIn("PREREQUISITE_NOT_DISCHARGED:D.BIND", result["blockers"])
        record["candidates"][0]["prerequisites"] = [{
            "id": "D.BIND", "state": "EARLIER_STAGE", "stage": 1,
            "dependent_stage": 2, "evidence": "repo:source/staged-binder"}]
        self.assertNotIn("PREREQUISITE_NOT_DISCHARGED:D.BIND", assess(
            record, grade="D", parent_release="fixed-parent-v1")["blockers"])
        record["candidates"][0]["unlocks"] = [{
            "capability": "E.COMPOSE", "via": "unspecified", "why": ""}]
        self.assertIn("SELECTED_TOPIC_UNLOCKS_NOT_TRACEABLE", assess(
            record, grade="D", parent_release="fixed-parent-v1")["blockers"])

    def test_parent_release_change_invalidates_old_review(self):
        record = proposal()
        result = assess(record, grade="D", parent_release="next-release-v2")
        self.assertIn("NEXT_GRADE_REVIEW_STALE_PARENT", result["blockers"])

    def test_selection_changes_reopen_all_prior_review_phases(self):
        record = proposal()
        record["decision"]["why_now"] += " and a new prerequisite"
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertIn("REVIEW_SCOPE_STALE:selection", result["blockers"])

    def test_missing_review_blocks_all_future_grades_without_fake_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_review("Z", Path(tmp))["status"], "BLOCKED")
            self.assertEqual(load_review("Z", Path(tmp))["blockers"],
                             ["NEXT_GRADE_REVIEW_MISSING"])

    def test_graduated_phase_does_not_reuse_admission_review_as_reflection(self):
        record = proposal()
        result = assess(record, grade="D", parent_release="fixed-parent-v1",
                        phase="retrospective")
        self.assertIn("REVIEW_PHASE_MISSING:retrospective", result["blockers"])


if __name__ == "__main__":
    unittest.main()
