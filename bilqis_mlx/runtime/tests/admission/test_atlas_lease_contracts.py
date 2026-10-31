"""Atlas lease contracts behavior through its public admission boundary."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionLease, issue_atlas_lease, persist_atlas_lease, read_atlas_lease,
)
from bilqis_mlx.runtime.tests.admission.test_atlas_admission import (
    _lease, _run, _scope, _signed, _REGISTRY,
)


class AtlasLeaseContractsTests(unittest.TestCase):
    def test_scope_signature_human_request_and_sets_fail_closed(self):
        for scope, human in ((replace(_scope(), signature_hex='0' * 128), True),
                             (_scope(), False), (_signed(replace(_scope(), audit_passed=False)), True),
                             (_signed(replace(_scope(), rights_compatible=False)), True)):
            with self.assertRaises(BilqisError):
                issue_atlas_lease('fixture-lease', _run(), scope, _lease().resource_ceiling,
                    requested_at=100, human_command_sha256='f' * 64, human_started=human,
                    registry=_REGISTRY)
        with self.assertRaises(BilqisError):
            replace(_scope(), source_family_ids=('same', 'same'))


    def test_lookup_only_scope_can_explicitly_allow_no_deterministic_operators(self):
        approval = _signed(replace(_scope(), operator_ids=()))
        lease = issue_atlas_lease('lookup-only', _run(), approval, _lease().resource_ceiling,
            requested_at=100, human_command_sha256='f' * 64, human_started=True, registry=_REGISTRY)
        self.assertEqual(lease.source_approval.operator_ids, ())
