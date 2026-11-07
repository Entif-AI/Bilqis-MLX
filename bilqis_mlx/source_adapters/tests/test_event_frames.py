"""Source authority, truth, encoding and fresh-example checks for event frames."""
from dataclasses import replace
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.source_adapters import event_frames as frames
from bilqis_mlx.verification.event_frames import independent_answer
from bilqis_mlx.live_grade_c import registry_graph


class EventFrameTests(unittest.TestCase):
    def test_production_identity_is_source_pinned_and_non_experimental(self):
        self.assertEqual(frames.ADAPTER_ID, 'source.ithkuil-event-frames/v1')
        self.assertEqual(frames.GENERATOR, 'bilqis.ithkuil-event-frame-constructor/v1')
        graph = frames.expanded_graph(registry_graph())
        for capability, spec in frames.SOURCE_SPECS.items():
            with self.subTest(capability=capability):
                self.assertNotIn('experiment', frames.SYMBOLS[capability])
                node = graph['nodes'][graph['tokens'].index(frames.SYMBOLS[capability])]
                self.assertEqual(node['semantic_id'], frames.SEMANTIC_IDS[capability])
                self.assertEqual(node['admission_receipt'], frames.source_contract_digest(capability))
                self.assertEqual(node['source'], 'https://ithkuil.net/New_Ithkuil_Lexicon.pdf')
                self.assertEqual(frames.source_senses()[capability]['lexicon_sense_id'],
                                 spec.sense_id)

    def test_source_contract_rejects_source_and_pdf_drift(self):
        capability = 'D.EVENT_OCCURRENCE'
        row = dict(frames.source_senses()[capability])
        pdf = frames.SOURCE_SPECS[capability].tracked_pdf_sha256
        frames._verify_source_row(capability, row, pdf)
        with self.assertRaises(BilqisError) as source_failure:
            frames._verify_source_row(
                capability, {**row, 'source_text_sha256': '0' * 64}, pdf)
        self.assertEqual(source_failure.exception.context['reason'],
                         'EVENT_FRAME_SOURCE_SENSE_DRIFT')
        with self.assertRaises(BilqisError) as pdf_failure:
            frames._verify_source_row(capability, row, '0' * 64)
        self.assertEqual(pdf_failure.exception.context['reason'],
                         'EVENT_FRAME_SOURCE_PDF_DRIFT')

    def test_provider_digest_binds_implementation(self):
        current = frames.provider_implementation_digest()
        changed = frames.provider_implementation_digest({
            'source_adapters/event_frames.py': b'changed-event-provider'})
        self.assertNotEqual(current, changed)

    def test_projected_graph_advances_one_prerequisite_closed_event_at_a_time(self):
        parent = registry_graph()
        occurrence = frames.projected_graph(parent, ('D.EVENT_OCCURRENCE',))
        self.assertIn(frames.SYMBOLS['D.EVENT_OCCURRENCE'], occurrence['tokens'])
        self.assertNotIn(frames.SYMBOLS['D.COMMENCEMENT'], occurrence['tokens'])
        with self.assertRaises(BilqisError) as blocked:
            frames.projected_graph(parent, ('D.COMMENCEMENT',))
        self.assertEqual(blocked.exception.context['reason'],
                         'EVENT_FRAME_CATALOG_PREREQUISITE_MISSING')
        commencement = frames.projected_graph(occurrence, ('D.COMMENCEMENT',))
        termination = frames.projected_graph(commencement, ('D.TERMINATION',))
        self.assertEqual(
            tuple(token for token in termination['tokens'] if token in frames.SYMBOLS.values()),
            tuple(frames.SYMBOLS.values()))

    def test_three_candidates_share_one_generator_and_checked_codec(self):
        graph = frames.expanded_graph(registry_graph())
        for capability in frames.SPECS:
            rows = frames.draw(None, graph, seed=349, each=32, capability=capability)
            self.assertEqual(len(rows), 32)
            self.assertEqual(sum(r['gold'] == 'TRUE' for r in rows), 16)
            self.assertTrue(all(frames.check(row, graph=graph) for row in rows))
            self.assertEqual(len({r['id'] for r in rows}), 32)
            changed = {**rows[0], 'gold': 'FALSE' if rows[0]['gold']=='TRUE' else 'TRUE'}
            self.assertFalse(frames.check(changed, graph=graph))
            fresh = frames.draw(None, graph, seed=350, each=32, capability=capability)
            self.assertNotEqual([r['id'] for r in rows], [r['id'] for r in fresh])

    def test_start_and_end_require_opposite_transition_directions(self):
        expected = {'D.EVENT_OCCURRENCE': (False, True, False, True),
                    'D.COMMENCEMENT': (False, True, False, False),
                    'D.TERMINATION': (False, False, True, False)}
        for cap, answers in expected.items():
            for (before, after), answer in zip(((False,False),(False,True),(True,False),(True,True)), answers):
                record = dict(task=frames.DIALECT, events=[['E0',before,after]],
                              capability=cap, query='E0')
                self.assertEqual(independent_answer(record), 'TRUE' if answer else 'FALSE')
