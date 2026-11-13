"""Active ABI custody is checked in addition to frame role/type validity."""
from dataclasses import replace
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout.output_sources import require_active_value
from bilqis_mlx.learning.atlas_readout.tests.plan_helpers import output_domain, concept, plan
from bilqis_mlx.learning.atlas_readout.tests.test_plan import standard_decisions


class OutputSourceTests(unittest.TestCase):
    def test_inactive_output_and_abi_release_swaps_reject(self):
        _, snapshot = output_domain()
        require_active_value(snapshot, concept())
        entry = replace(snapshot.abi_entries[11], active=False)
        inactive = replace(snapshot, abi_entries=snapshot.abi_entries[:11] + (entry,))
        for source, value in ((inactive, concept()), (snapshot, replace(concept(), abi_index=10)),
                              (snapshot, replace(concept(), semantic_release='e'*64))):
            with self.assertRaises(BilqisError):
                require_active_value(source, value)
        with self.assertRaises(BilqisError):
            replace(plan(standard_decisions()), snapshot=inactive)

    def test_malformed_snapshot_cannot_escape_as_index_error(self):
        _, snapshot = output_domain()
        broken = replace(snapshot, abi_entries=())
        with self.assertRaises(BilqisError):
            require_active_value(broken, concept())
