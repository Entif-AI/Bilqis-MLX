"""Darwin path-traversal proof for the fixed C09 host trust root."""
import errno
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin


def _info(*, directory=False, uid=0, mode=0o600, size=32, dev=1, ino=2):
    kind = stat.S_IFDIR if directory else stat.S_IFREG
    return SimpleNamespace(
        st_mode=kind | mode, st_uid=uid, st_size=size, st_dev=dev, st_ino=ino)


class DarwinHostPathTests(unittest.TestCase):
    def test_fixed_opener_uses_exact_etc_alias_and_fd_relative_chain(self):
        opened = iter((10, 11, 12, 13, 14, 15))
        calls = []

        def open_fd(name, flags, **kwargs):
            calls.append((name, flags, kwargs.get("dir_fd")))
            return next(opened)

        def safe(fd, *, directory):
            return _info(directory=directory, size=64, dev=1, ino=2 if fd == 12 else fd)

        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="private/etc"), \
                patch.object(darwin.os, "stat", return_value=_info(directory=True, dev=1, ino=2)), \
                patch.object(darwin.os, "open", side_effect=open_fd), \
                patch.object(darwin.os, "fstat", return_value=_info(directory=True, dev=1, ino=2)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor", side_effect=safe):
            result = darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(result, 15)
        self.assertEqual(
            [(name, parent) for name, _flags, parent in calls],
            [("/", None), ("private", 10), ("etc", 11), ("entif-ai", 12),
             ("bilqis", 13), ("source-authority-registry.json", 14)])

    def test_missing_administered_component_is_required_not_invalid(self):
        def open_fd(name, _flags, **_kwargs):
            if name == "entif-ai":
                raise FileNotFoundError(errno.ENOENT, "missing")
            return {"/": 10, "private": 11, "etc": 12}[name]

        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="private/etc"), \
                patch.object(darwin.os, "stat", return_value=_info(directory=True, dev=1, ino=2)), \
                patch.object(darwin.os, "open", side_effect=open_fd), \
                patch.object(darwin.os, "fstat", return_value=_info(directory=True, dev=1, ino=2)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor",
                             return_value=_info(directory=True, dev=1, ino=2)), \
                self.assertRaises(BilqisError) as caught:
            darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED")

    def test_bad_etc_alias_and_physical_inode_mismatch_reject(self):
        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="not-private/etc"), \
                self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=128)

        opened = iter((10, 11, 12))
        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="private/etc"), \
                patch.object(darwin.os, "stat", return_value=_info(directory=True, dev=1, ino=999)), \
                patch.object(darwin.os, "open", side_effect=lambda *_a, **_k: next(opened)), \
                patch.object(darwin.os, "fstat", return_value=_info(directory=True, dev=1, ino=12)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor",
                             side_effect=lambda fd, *, directory: _info(
                                 directory=directory, dev=1, ino=fd)), \
                self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=128)

    def test_symlinked_admin_component_and_oversized_final_file_reject(self):
        def symlink_open(name, _flags, **_kwargs):
            if name == "entif-ai":
                raise OSError(errno.ELOOP, "symlink")
            return {"/": 10, "private": 11, "etc": 12}[name]

        common = (
            patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)),
            patch.object(darwin.os, "readlink", return_value="private/etc"),
            patch.object(darwin.os, "stat", return_value=_info(directory=True, dev=1, ino=12)),
        )
        with common[0], common[1], common[2], \
                patch.object(darwin.os, "open", side_effect=symlink_open), \
                patch.object(darwin.os, "fstat", return_value=_info(directory=True, dev=1, ino=12)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor",
                             side_effect=lambda fd, *, directory: _info(
                                 directory=directory, dev=1, ino=12 if fd == 12 else fd)), \
                self.assertRaises(BilqisError) as caught:
            darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")

        opened = iter((20, 21, 22, 23, 24, 25))
        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="private/etc"), \
                patch.object(darwin.os, "stat", return_value=_info(directory=True, dev=1, ino=22)), \
                patch.object(darwin.os, "open", side_effect=lambda *_a, **_k: next(opened)), \
                patch.object(darwin.os, "fstat", return_value=_info(directory=True, dev=1, ino=22)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor",
                             side_effect=lambda fd, *, directory: _info(
                                 directory=directory, dev=1, ino=22 if fd == 22 else fd,
                                 size=129 if not directory else 32)), \
                self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=128)

    def test_failure_closes_every_opened_ancestor(self):
        closed = Mock()

        def open_fd(name, _flags, **_kwargs):
            if name == "bilqis":
                raise OSError(errno.EACCES, "denied")
            return {"/": 30, "private": 31, "etc": 32, "entif-ai": 33}[name]

        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="private/etc"), \
                patch.object(darwin.os, "stat", return_value=_info(directory=True, dev=1, ino=32)), \
                patch.object(darwin.os, "open", side_effect=open_fd), \
                patch.object(darwin.os, "fstat", return_value=_info(directory=True, dev=1, ino=32)), \
                patch.object(darwin.os, "close", closed), \
                patch.object(darwin, "require_safe_host_descriptor",
                             side_effect=lambda fd, *, directory: _info(
                                 directory=directory, dev=1, ino=32 if fd == 32 else fd)), \
                self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual([call.args[0] for call in closed.call_args_list], [33, 32, 31, 30])


if __name__ == "__main__":
    unittest.main()
