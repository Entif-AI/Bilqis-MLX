"""Source-authenticated requalification behavior."""
import unittest

from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    BilqisError, CapabilitySupport, DependencyKind, RequalificationLedger,
    RequalificationStatus, _chain, _event, _ref,
    apply_correction, mark_affected_capabilities, replace,
)


class RequalificationTests(unittest.TestCase):
    def test_invalidated_learned_support_queues_targeted_source_tasks_without_weight_edits(self):
        index, _, _ = _chain()
        motif = index.node("motif:alpha")
        rights = _ref(DependencyKind.RIGHTS, "rights:motif")
        index = index.replace_node(replace(
            motif, immediate_dependencies=tuple(sorted((
                *motif.immediate_dependencies, rights,
            )))))
        queue = apply_correction(_event(rights), index)
        original_alpha = CapabilitySupport(
            capability_id="capability:alpha",
            support_artifact_ids=("capability:alpha",),
            source_anchor_ids=("source:alpha",),
            retained_generation_sha256="1" * 64,
            observation_ids=("observation:alpha:1",),
            status=RequalificationStatus.QUALIFIED,
        )
        original_beta = CapabilitySupport(
            capability_id="capability:beta",
            support_artifact_ids=("feature:beta",),
            source_anchor_ids=("source:beta",),
            retained_generation_sha256="2" * 64,
            observation_ids=("observation:beta:1",),
            status=RequalificationStatus.QUALIFIED,
        )
        ledger = RequalificationLedger((original_alpha, original_beta))
        update = mark_affected_capabilities(ledger, index, queue)
        self.assertEqual(update.affected_capability_ids,
                         ("capability:alpha",))
        self.assertEqual(update.ledger.capability(
            "capability:alpha").status,
            RequalificationStatus.REQUALIFICATION_REQUIRED)
        self.assertEqual(update.ledger.capability("capability:beta"),
                         original_beta)
        self.assertEqual(update.ledger.historical, (original_alpha,))
        self.assertEqual(update.ledger.capability(
            "capability:alpha").retained_generation_sha256, "1" * 64)
        self.assertEqual(update.ledger.capability(
            "capability:alpha").observation_ids,
            ("observation:alpha:1",))
        self.assertEqual(len(update.new_source_tasks), 1)
        self.assertEqual(update.new_source_tasks[0].source_anchor_ids,
                         ("source:alpha",))
        self.assertEqual(update.new_source_tasks[0].capability_id,
                         "capability:alpha")
        self.assertEqual(len(update.new_c10_intents), 1)
        self.assertEqual(update.new_c10_intents[0].namespace,
                         "bamf.c09.requalification")
        self.assertEqual(update.new_c10_intents[0].delivery_state,
                         "PENDING_C10")
        with self.assertRaises(BilqisError) as caught:
            replace(update.new_source_tasks[0], task_id="0" * 64)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_SOURCE_TASK_INVALID")
        with self.assertRaises(BilqisError) as caught:
            replace(update.new_c10_intents[0], payload_digest="0" * 64)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_C10_INTENT_INVALID")
        again = mark_affected_capabilities(update.ledger, index, queue)
        self.assertEqual(again.new_source_tasks, ())
        self.assertEqual(again.new_c10_intents, ())
        self.assertEqual(again.ledger, update.ledger)
        self.assertEqual(ledger.capability("capability:alpha"), original_alpha)

    def test_prior_unrelated_ineligibility_does_not_contaminate_new_correction(self):
        index, _, source_b = _chain()
        index = index.replace_node(replace(
            index.node("motif:alpha"), eligible=False))
        ledger = RequalificationLedger((
            CapabilitySupport(
                capability_id="capability:alpha",
                support_artifact_ids=("capability:alpha",),
                source_anchor_ids=("source:alpha",),
                retained_generation_sha256="1" * 64,
                observation_ids=("observation:alpha:1",),
                status=RequalificationStatus.QUALIFIED,
            ),
        ))
        unrelated = mark_affected_capabilities(
            ledger, index, apply_correction(_event(source_b), index))
        self.assertEqual(unrelated.affected_capability_ids, ())
        self.assertEqual(unrelated.new_source_tasks, ())
        self.assertEqual(unrelated.new_c10_intents, ())
        self.assertEqual(unrelated.ledger, ledger)
