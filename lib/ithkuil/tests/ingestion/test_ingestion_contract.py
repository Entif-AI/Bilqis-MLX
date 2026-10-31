from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
"""Normative workflow surface checks; no parser, compiler or graph execution."""

import json
from pathlib import Path
import unittest

ROOT = ITHKUIL_ROOT
REPO = ROOT.parents[1]


class IngestionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / 'ingestion_contract.json').read_text())

    def test_governance_and_authority_boundaries(self):
        c = self.contract
        self.assertEqual(c['schema'], 'bilqis.ithkuil.ingestion-contract/v1')
        self.assertEqual(c['version'], '1.0.0')
        self.assertEqual(c['governance']['authority_mode'], 'public_only')
        self.assertEqual(c['governance']['external_write_posture'], 'classification_required')
        self.assertFalse(c['llm_semantic_interpretation'])
        self.assertEqual(c['forbidden'], ['invent_semantics', 'override_pins', 'curriculum_admission',
                                         'neural_training', 'bypass_conformance', 'implicit_graph_target',
                                         'automatic_reset', 'automatic_publication'])
        self.assertEqual(set(c['authority_domains']),
                         {'source', 'relational_ir', 'semantic_rdf', 'conformance', 'falkor', 'curriculum'})

    def test_stages_reuse_existing_owners_and_name_failure_receipts(self):
        stages = self.contract['stages']
        self.assertEqual(set(stages), {'inspect', 'source', 'core', 'conformance', 'materialize', 'readback'})
        for stage in stages.values():
            for module in stage['modules']:
                self.assertTrue((REPO / (module.replace('.', '/') + '.py')).is_file(), module)
            for required in ('preconditions', 'success', 'failures', 'retry', 'prior_outputs'):
                self.assertTrue(stage[required], required)
        self.assertEqual(stages['materialize']['input_artifact'], 'conformance_evidence_bundle')
        self.assertNotEqual(stages['core']['output_artifact'], stages['materialize']['input_artifact'])
        self.assertTrue(stages['materialize']['explicit_graph_authorization'])
        self.assertEqual(stages['readback']['write_class'], 'read_only')
        self.assertFalse(self.contract['source_fetch']['invoke_snapshot_main'])

    def test_supported_optional_and_rejected_requests_have_literal_routes(self):
        examples = self.contract['examples']
        self.assertEqual(examples['rebuild_pinned']['stages'], ['inspect', 'source'])
        self.assertEqual(examples['compile_and_check']['stages'], ['inspect', 'core', 'conformance'])
        self.assertEqual(examples['optional_graph']['stages'], ['inspect', 'conformance', 'materialize', 'readback'])
        self.assertEqual(examples['optional_graph']['required_authorization'], 'exact_graph_and_owner')
        self.assertEqual(examples['invent_missing']['result'], 'reject')
        self.assertEqual(examples['train']['result'], 'route_outside_skill')
        for name in ('rebuild_pinned', 'compile_and_check'):
            self.assertNotIn('materialize', examples[name]['stages'])


if __name__ == '__main__':
    unittest.main()
