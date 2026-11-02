"""Source-bound world rule fixtures use explicit facts, never inferred causes."""
import copy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.source_adapters.world_rules import (
    CAPABILITIES, draw, check, projected_graph, registered_adapter, verify_source,
)
from bilqis_mlx.vocabulary_growth import digest


class QualifiedWorldSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = registry_graph()
        cls.graph = projected_graph(cls.parent)

    def test_source_is_direct_causation_with_scoped_formal_morphology(self):
        witness = verify_source()
        self.assertEqual(witness['sense_id'], 'LEXSENSE-59819df75e3137')
        self.assertEqual(witness['grammar_section'], 'NI-WEB-CH04:4.2.7')
        self.assertEqual(witness['morphology'], 'NOT_REALIZED')
        self.assertEqual(self.graph['tokens'][:len(self.parent['tokens'])], self.parent['tokens'])
        self.assertEqual(self.graph['nodes'][:len(self.parent['nodes'])], self.parent['nodes'])

    def test_provider_fingerprint_binds_both_executable_implementation_files(self):
        root = Path(__file__).resolve().parents[4]
        files = (
            ("bilqis_mlx/source_adapters/world_rules.py",
             root / "bilqis_mlx/source_adapters/world_rules.py"),
            ("bilqis_mlx/source_adapters/_world/oracle.py",
             root / "bilqis_mlx/source_adapters/_world/oracle.py"),
        )
        expected = digest({
            "source": verify_source(),
            "files": tuple(
                (relative, hashlib.sha256(path.read_bytes()).hexdigest())
                for relative, path in files),
        })
        oracle_only = digest({
            "source": verify_source(),
            "files": ((files[1][0],
                       hashlib.sha256(files[1][1].read_bytes()).hexdigest()),),
        })
        actual = registered_adapter().descriptor.implementation_sha256
        self.assertEqual(actual, expected)
        self.assertNotEqual(actual, oracle_only)

    def test_provider_fingerprint_binds_full_semantic_source_rows(self):
        from bilqis_mlx.source_adapters import world_rules
        baseline = registered_adapter().descriptor.implementation_sha256
        original = world_rules._row

        def drifted(path, key, value):
            row = dict(original(path, key, value))
            row["unvalidated_semantic_field"] = "DRIFT"
            return row

        with patch.object(world_rules, "_row", drifted):
            changed = registered_adapter().descriptor.implementation_sha256
        self.assertNotEqual(changed, baseline)

    def test_registered_adapter_ignores_runtime_draw_check_rebinding(self):
        from bilqis_mlx.source_adapters import world_rules
        baseline = registered_adapter()
        with patch.object(world_rules, "draw", lambda **_: ({"forged": True},)), \
                patch.object(world_rules, "check", lambda *_args, **_kwargs: True):
            rebound = registered_adapter()
        self.assertEqual(rebound.descriptor, baseline.descriptor)
        self.assertIs(rebound.draw, baseline.draw)
        self.assertIs(rebound.check, baseline.check)

    def test_all_four_rules_have_fresh_independently_checked_source_rows(self):
        for capability in CAPABILITIES:
            with self.subTest(capability=capability):
                rows = draw(graph=self.graph, capability=capability, seed=420, each=12)
                other = draw(graph=self.graph, capability=capability, seed=421, each=12)
                self.assertEqual(len(rows), 12)
                self.assertTrue(all(check(row, graph=self.graph) for row in rows))
                self.assertNotEqual(rows, other)
                self.assertEqual({row['gold'] for row in rows}, {'TRUE', 'FALSE'})
                self.assertTrue(all(row['source_contract_sha256'] == registered_adapter().descriptor.implementation_sha256 for row in rows))

    def test_gold_token_and_source_forgery_reject(self):
        row = draw(graph=self.graph, capability='WORLD.DIRECT_CAUSE', seed=9, each=1)[0]
        for changed in (
                {**row, 'gold': 'FALSE' if row['gold'] == 'TRUE' else 'TRUE'},
                {**row, 'tokens': row['tokens'][:-1]},
                {**row, 'source_contract_sha256': 'f' * 64}):
            with self.subTest(changed=changed):
                self.assertFalse(check(changed, graph=self.graph))

    def test_time_order_and_indirect_chain_do_not_establish_direct_cause(self):
        from bilqis_mlx.source_adapters._world.oracle import answer
        row = draw(graph=self.graph, capability='WORLD.DIRECT_CAUSE', seed=3, each=1)[0]
        record = copy.deepcopy(row['record'])
        events = sorted(record['events'], key=lambda item: item['time'])
        first, middle, last = [event['id'] for event in events[:3]]
        record['direct_causes'] = [[first, middle], [middle, last]]
        record['query'] = {'kind': 'DIRECT_CAUSE', 'left': first, 'right': last}
        self.assertEqual(answer(record), 'FALSE')
        record['query']['right'] = middle
        self.assertEqual(answer(record), 'TRUE')
