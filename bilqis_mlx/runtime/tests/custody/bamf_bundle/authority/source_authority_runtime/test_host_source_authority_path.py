"""Path-selection proof for the fixed ordinary-user C09 authority store."""
import os
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin


def _file_info(*, uid=501, size=64):
    return SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=uid, st_size=size)


class DarwinUserPathTests(unittest.TestCase):
    def test_registry_path_comes_from_effective_account_not_home_env_or_cwd(self):
        calls = []

        def open_fd(path, flags):
            calls.append((path, flags))
            return 7

        with patch.dict(os.environ, {"HOME": "/tmp/attacker-home"}), \
                patch.object(darwin.os, "geteuid", return_value=501), \
                patch.object(darwin.pwd, "getpwuid", return_value=SimpleNamespace(
                    pw_dir="/Users/operator")), \
                patch.object(darwin.os, "getcwd", return_value="/tmp/attacker-cwd"), \
                patch.object(darwin.os, "open", side_effect=open_fd), \
                patch.object(darwin.os, "fstat", return_value=_file_info()), \
                patch.object(darwin.os, "close"):
            fd = darwin.open_host_source_authority_registry_fd(max_bytes=128)

        self.assertEqual(fd, 7)
        self.assertEqual(
            calls[0][0],
            "/Users/operator/.entif-ai/bilqis/source-authority-registry.json",
        )
        self.assertTrue(calls[0][1] & os.O_NOFOLLOW)
        self.assertNotIn("attacker", calls[0][0])

    def test_registry_and_signer_share_fixed_account_directory(self):
        calls = []

        def open_fd(path, flags):
            calls.append(path)
            return len(calls) + 10

        with patch.object(darwin.os, "geteuid", return_value=501), \
                patch.object(darwin.pwd, "getpwuid", return_value=SimpleNamespace(
                    pw_dir="/Users/operator")), \
                patch.object(darwin.os, "open", side_effect=open_fd), \
                patch.object(darwin.os, "fstat", return_value=_file_info()), \
                patch.object(darwin.os, "close"):
            registry_fd = darwin.open_host_source_authority_registry_fd(max_bytes=128)
            signer_fd = darwin.open_host_source_authority_signer_fd(max_bytes=128)

        self.assertEqual((registry_fd, signer_fd), (11, 12))
        self.assertEqual(calls, [
            "/Users/operator/.entif-ai/bilqis/source-authority-registry.json",
            "/Users/operator/.entif-ai/bilqis/source-authority-signer.json",
        ])

    def test_reader_api_exposes_no_path_argument(self):
        with self.assertRaises(TypeError):
            darwin.open_host_source_authority_registry_fd(  # type: ignore[call-arg]
                max_bytes=128, path="/tmp/alternate.json")


if __name__ == "__main__":
    unittest.main()
