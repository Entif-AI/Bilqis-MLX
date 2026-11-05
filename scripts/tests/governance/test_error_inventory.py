"""Raw inventory retains identities when error messages use constants."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

from scripts import error_control_plane


class ErrorInventoryTests(unittest.TestCase):
    def test_quality_base_ref_prefers_explicit_then_environment(self):
        environment = {"BILQIS_QUALITY_BASE_REF": "reviewed-base"}
        self.assertEqual(
            error_control_plane.quality_base_ref("explicit-base", environment),
            "explicit-base",
        )
        self.assertEqual(
            error_control_plane.quality_base_ref(None, environment),
            "reviewed-base",
        )
        self.assertIsNone(error_control_plane.quality_base_ref(None, {}))

    def test_literal_and_module_constants_group_as_same_identity(self):
        source = '''\
MESSAGE = "EXAMPLE_CODE: details"
ANNOTATED: str = "EXAMPLE_CODE: details"
raise ValueError("EXAMPLE_CODE: details")
raise ValueError(MESSAGE)
raise ValueError(ANNOTATED)
raise ValueError(UNKNOWN)
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "example.py"
            path.write_text(source, encoding="utf-8")
            with patch.object(error_control_plane, "ROOT", root), patch(
                "operations.operator_contract_audit._repository_python_files",
                return_value=[path],
            ):
                sites = error_control_plane.raw_error_sites()

        self.assertEqual(sites, ({
            "path": "example.py",
            "exception": "ValueError",
            "expression": "'EXAMPLE_CODE: details'",
            "code_hint": "EXAMPLE_CODE",
            "count": 3,
        },))
