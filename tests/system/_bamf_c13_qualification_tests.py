"""C13.2 qualification receipt contracts."""
from __future__ import annotations

from unittest.mock import patch
import unittest

from scripts.bamf.c13.qualification import CommandReceipt, qualify_c13


class BamfC13QualificationTests(unittest.TestCase):
    def test_qualification_records_exact_heads_resource_and_advisory_guard(self):
        passing = CommandReceipt(
            "required", ("true",), True, 0, 7, "a" * 64, "b" * 64, 17, "ok", "")
        advisory = CommandReceipt(
            "historical-abi", ("false",), False, 2, 9, "c" * 64, "d" * 64, 19,
            "advisory", "expected sha absent")
        with patch("scripts.bamf.c13.qualification._git", side_effect=("1" * 40, "2" * 40)), \
                patch("scripts.bamf.c13.qualification._commands", return_value=(
                    ("required", ("true",), True),
                    ("historical-abi", ("false",), False),
                )), patch("scripts.bamf.c13.qualification._run", side_effect=(passing, advisory)), \
                patch("scripts.bamf.c13.qualification._memory_bytes", return_value=96 * 1024 ** 3):
            receipt = qualify_c13(base_ref="base", prerequisite_sha256="3" * 40)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.head_sha256, "1" * 40)
        self.assertEqual(receipt.base_sha256, "2" * 40)
        self.assertEqual(receipt.prerequisite_sha256, "3" * 40)
        self.assertEqual(receipt.host_memory_bytes, 96 * 1024 ** 3)
        self.assertEqual(receipt.commands, (passing, advisory))

    def test_required_guard_failure_fails_qualification(self):
        failed = CommandReceipt(
            "required", ("false",), True, 1, 4, "a" * 64, "b" * 64, 13,
            "failed", "owner guard failed")
        with patch("scripts.bamf.c13.qualification._git", side_effect=("1" * 40, "2" * 40)), \
                patch("scripts.bamf.c13.qualification._commands", return_value=(("required", ("false",), True),)), \
                patch("scripts.bamf.c13.qualification._run", return_value=failed):
            receipt = qualify_c13(base_ref="base", prerequisite_sha256="3" * 40)
        self.assertEqual(receipt.status, "FAIL")


__all__ = ("BamfC13QualificationTests",)
