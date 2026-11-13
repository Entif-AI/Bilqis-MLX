"""Ordinary-user custody checks for the fixed Darwin C09 files."""
import errno
import os
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin


def _info(*, uid=501, mode=0o600, size=32, directory=False):
    kind = stat.S_IFDIR if directory else stat.S_IFREG
    return SimpleNamespace(st_mode=kind | mode, st_uid=uid, st_size=size)


class DarwinUserCustodyTests(unittest.TestCase):
    def test_root_execution_is_not_a_required_or_supported_path(self):
        with patch.object(darwin.os, "geteuid", return_value=0), \
                self.assertRaises(BilqisError) as caught:
            darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID",
        )

    def test_missing_file_reports_required(self):
        with patch.object(darwin.os, "geteuid", return_value=501), \
                patch.object(darwin.pwd, "getpwuid", return_value=SimpleNamespace(
                    pw_dir="/Users/operator")), \
                patch.object(
                    darwin.os, "open",
                    side_effect=FileNotFoundError(errno.ENOENT, "missing")), \
                self.assertRaises(BilqisError) as caught:
            darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED",
        )

    def test_wrong_owner_type_and_size_fail_closed(self):
        candidates = (
            _info(uid=777),
            _info(directory=True),
            _info(size=0),
            _info(size=129),
        )
        for info in candidates:
            with self.subTest(info=info), \
                    patch.object(darwin.os, "geteuid", return_value=501), \
                    patch.object(darwin.pwd, "getpwuid", return_value=SimpleNamespace(
                        pw_dir="/Users/operator")), \
                    patch.object(darwin.os, "open", return_value=7), \
                    patch.object(darwin.os, "fstat", return_value=info), \
                    patch.object(darwin.os, "close"), \
                    self.assertRaises(BilqisError):
                darwin.open_host_source_authority_registry_fd(max_bytes=128)

    def test_symlink_final_component_fails_closed(self):
        with patch.object(darwin.os, "geteuid", return_value=501), \
                patch.object(darwin.pwd, "getpwuid", return_value=SimpleNamespace(
                    pw_dir="/Users/operator")), \
                patch.object(
                    darwin.os, "open", side_effect=OSError(errno.ELOOP, "symlink")), \
                self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=128)


if __name__ == "__main__":
    unittest.main()
