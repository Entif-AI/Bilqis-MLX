from copy import deepcopy
import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.delivery import load_manifest_record, seal_manifest
from bilqis_mlx.runtime.delivery.tests.test_contracts import manifest


class DeliveryCodecTests(unittest.TestCase):
    def test_sealed_manifest_roundtrips_with_exact_content_digest(self):
        value = manifest()
        sealed = seal_manifest(value)
        self.assertEqual(sealed["manifest_sha256"], value.digest())
        self.assertEqual(load_manifest_record(sealed), value)

    def test_payload_mutation_rejects_before_publication(self):
        sealed = seal_manifest(manifest())
        changed = deepcopy(sealed)
        changed["software_delivery_status"] = "BLOCKED"
        with self.assertRaises(BilqisError) as caught:
            load_manifest_record(changed)
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

    def test_unknown_fields_are_not_silently_accepted(self):
        sealed = seal_manifest(manifest())
        sealed["helpful_note"] = "not part of the authority contract"
        with self.assertRaises(BilqisError) as caught:
            load_manifest_record(sealed)
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)


if __name__ == "__main__":
    unittest.main()
