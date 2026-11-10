"""Phase-A proof for fixed Darwin C09 host custody and branch resolution."""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from bilqis_mlx.runtime.bamf_bundle import source_authority_custody as custody
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, provision_source_authority_registry,
    with_source_authority_registry,
)
from bilqis_mlx.semantics.tests.core.test_atlas_export_clearance import REGISTRY


class _AclLibrary:
    def __init__(self, entries=(), *, absent=False, first_error=None):
        self.entries = tuple(entries)
        self.absent = absent
        self.first_error = first_error
        self.index = -1

    def acl_get_fd_np(self, _fd, _kind):
        if self.absent:
            ctypes.set_errno(errno.ENOENT)
            return None
        return 1

    def acl_get_entry(self, _acl, entry_id, output):
        if entry_id == darwin.ACL_FIRST_ENTRY:
            if self.first_error is not None:
                ctypes.set_errno(self.first_error)
                return -1
            self.index = 0
        else:
            self.index += 1
        if self.index >= len(self.entries):
            ctypes.set_errno(errno.EINVAL)
            return -1
        output._obj.value = 10 + self.index
        return 0

    def _entry_index(self, handle):
        value = handle.value if hasattr(handle, "value") else handle
        return int(value) - 10

    def acl_get_tag_type(self, handle, output):
        output._obj.value = self.entries[self._entry_index(handle)][0]
        return 0

    def acl_get_qualifier(self, handle):
        return 100 + self._entry_index(handle)

    def mbr_uuid_to_id(self, qualifier, principal, principal_type):
        value = qualifier.value if hasattr(qualifier, "value") else qualifier
        entry = self.entries[int(value) - 100]
        principal_type._obj.value = entry[1]
        principal._obj.value = entry[2]
        return 0

    def acl_get_permset(self, handle, output):
        output._obj.value = 200 + self._entry_index(handle)
        return 0

    def acl_get_perm_np(self, permset, permission):
        value = permset.value if hasattr(permset, "value") else permset
        names = self.entries[int(value) - 200][3]
        return int(any(darwin._PERMISSIONS[name] == permission for name in names))

    def acl_free(self, _value):
        return 0


def _info(*, directory=False, uid=0, mode=0o600, size=32, dev=1, ino=2):
    kind = stat.S_IFDIR if directory else stat.S_IFREG
    return SimpleNamespace(
        st_mode=kind | mode, st_uid=uid, st_size=size, st_dev=dev, st_ino=ino)


class DarwinHostBoundaryTests(unittest.TestCase):
    def test_no_extended_acl_is_exact_null_enoent(self):
        with patch.object(darwin, "_libsystem", return_value=_AclLibrary(absent=True)):
            self.assertEqual(darwin.read_extended_acl(7), ())

    def test_non_null_acl_must_have_a_first_entry(self):
        with patch.object(
                darwin, "_libsystem",
                return_value=_AclLibrary(first_error=errno.EINVAL)), \
                self.assertRaises(BilqisError):
            darwin.read_extended_acl(7)

    def test_acl_iteration_resolves_principals_and_mutation_permissions(self):
        library = _AclLibrary((
            (darwin.ACL_EXTENDED_ALLOW, darwin.ID_TYPE_UID, 0, {"ACL_WRITE_DATA"}),
            (darwin.ACL_EXTENDED_DENY, darwin.ID_TYPE_GID, 80, {"ACL_DELETE"}),
        ))
        with patch.object(darwin, "_libsystem", return_value=library):
            entries = darwin.read_extended_acl(7)
        self.assertEqual(entries[0].principal_kind, "UID")
        self.assertEqual(entries[0].principal_id, 0)
        self.assertEqual(entries[0].permissions, frozenset({"ACL_WRITE_DATA"}))
        self.assertEqual(entries[1].tag, darwin.ACL_EXTENDED_DENY)

    def test_descriptor_rejects_non_root_mode_and_mutating_allow(self):
        safe = _info()
        dangerous = darwin.DarwinAclEntry(
            darwin.ACL_EXTENDED_ALLOW, "UID", 501,
            frozenset({"ACL_WRITE_SECURITY"}))
        for info, acl in (
            (_info(uid=501), ()),
            (_info(mode=0o620), ()),
            (safe, (dangerous,)),
            (safe, (darwin.DarwinAclEntry(
                darwin.ACL_EXTENDED_ALLOW, "GID", 0,
                frozenset({"ACL_APPEND_DATA"})),)),
        ):
            with self.subTest(info=info, acl=acl), \
                    patch.object(darwin.os, "fstat", return_value=info), \
                    patch.object(darwin, "read_extended_acl", return_value=acl), \
                    self.assertRaises(BilqisError):
                darwin.require_safe_host_descriptor(7, directory=False)

    def test_every_named_mutation_right_rejects_non_root_allow(self):
        info = _info()
        for permission in sorted(darwin._MUTATION_PERMISSIONS):
            acl = (darwin.DarwinAclEntry(
                darwin.ACL_EXTENDED_ALLOW, "UID", 501,
                frozenset({permission})),)
            with self.subTest(permission=permission), \
                    patch.object(darwin.os, "fstat", return_value=info), \
                    patch.object(darwin, "read_extended_acl", return_value=acl), \
                    self.assertRaises(BilqisError):
                darwin.require_safe_host_descriptor(7, directory=False)

    def test_descriptor_rejects_wrong_object_type(self):
        for info, directory in ((_info(directory=True), False), (_info(), True)):
            with self.subTest(directory=directory), \
                    patch.object(darwin.os, "fstat", return_value=info), \
                    patch.object(darwin, "read_extended_acl", return_value=()), \
                    self.assertRaises(BilqisError):
                darwin.require_safe_host_descriptor(7, directory=directory)

    def test_descriptor_allows_read_only_user_and_mutating_root_allow(self):
        acl = (
            darwin.DarwinAclEntry(darwin.ACL_EXTENDED_ALLOW, "UID", 501, frozenset()),
            darwin.DarwinAclEntry(
                darwin.ACL_EXTENDED_ALLOW, "UID", 0,
                frozenset({"ACL_DELETE_CHILD"})),
        )
        info = _info()
        with patch.object(darwin.os, "fstat", return_value=info), \
                patch.object(darwin, "read_extended_acl", return_value=acl):
            self.assertIs(darwin.require_safe_host_descriptor(7, directory=False), info)

    def test_fixed_opener_uses_exact_etc_alias_and_fd_relative_chain(self):
        opened = iter((10, 11, 12, 13, 14, 15))
        calls = []

        def open_fd(name, flags, **kwargs):
            calls.append((name, flags, kwargs.get("dir_fd")))
            return next(opened)

        def safe(fd, *, directory):
            return _info(directory=directory, size=64,
                         dev=1, ino=2 if fd == 12 else fd)

        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="private/etc"), \
                patch.object(darwin.os, "stat", return_value=_info(
                    directory=True, dev=1, ino=2)), \
                patch.object(darwin.os, "open", side_effect=open_fd), \
                patch.object(darwin.os, "fstat", return_value=_info(
                    directory=True, dev=1, ino=2)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor", side_effect=safe):
            result = darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(result, 15)
        self.assertEqual(
            [(name, parent) for name, _flags, parent in calls],
            [("/", None), ("private", 10), ("etc", 11),
             ("entif-ai", 12), ("bilqis", 13),
             ("source-authority-registry.json", 14)],
        )

    def test_missing_administered_component_is_required_not_invalid(self):
        def open_fd(name, _flags, **_kwargs):
            if name == "entif-ai":
                raise FileNotFoundError(errno.ENOENT, "missing")
            return {"/": 10, "private": 11, "etc": 12}[name]

        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="private/etc"), \
                patch.object(darwin.os, "stat", return_value=_info(
                    directory=True, dev=1, ino=2)), \
                patch.object(darwin.os, "open", side_effect=open_fd), \
                patch.object(darwin.os, "fstat", return_value=_info(
                    directory=True, dev=1, ino=2)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor", return_value=_info(
                    directory=True, dev=1, ino=2)), \
                self.assertRaises(BilqisError) as caught:
            darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED",
        )

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
                patch.object(darwin.os, "stat", return_value=_info(
                    directory=True, dev=1, ino=999)), \
                patch.object(darwin.os, "open", side_effect=lambda *_a, **_k: next(opened)), \
                patch.object(darwin.os, "fstat", return_value=_info(
                    directory=True, dev=1, ino=12)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor", side_effect=lambda fd, *, directory: _info(
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
            patch.object(darwin.os, "stat", return_value=_info(
                directory=True, dev=1, ino=12)),
        )
        with common[0], common[1], common[2], \
                patch.object(darwin.os, "open", side_effect=symlink_open), \
                patch.object(darwin.os, "fstat", return_value=_info(
                    directory=True, dev=1, ino=12)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor", side_effect=lambda fd, *, directory: _info(
                    directory=directory, dev=1, ino=12 if fd == 12 else fd)), \
                self.assertRaises(BilqisError) as caught:
            darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID",
        )

        opened = iter((20, 21, 22, 23, 24, 25))
        with patch.object(darwin.os, "lstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(darwin.os, "readlink", return_value="private/etc"), \
                patch.object(darwin.os, "stat", return_value=_info(
                    directory=True, dev=1, ino=22)), \
                patch.object(darwin.os, "open", side_effect=lambda *_a, **_k: next(opened)), \
                patch.object(darwin.os, "fstat", return_value=_info(
                    directory=True, dev=1, ino=22)), \
                patch.object(darwin.os, "close"), \
                patch.object(darwin, "require_safe_host_descriptor", side_effect=lambda fd, *, directory: _info(
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
                patch.object(darwin.os, "stat", return_value=_info(
                    directory=True, dev=1, ino=32)), \
                patch.object(darwin.os, "open", side_effect=open_fd), \
                patch.object(darwin.os, "fstat", return_value=_info(
                    directory=True, dev=1, ino=32)), \
                patch.object(darwin.os, "close", closed), \
                patch.object(darwin, "require_safe_host_descriptor", side_effect=lambda fd, *, directory: _info(
                    directory=directory, dev=1, ino=32 if fd == 32 else fd)), \
                self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=128)
        self.assertEqual(
            [call.args[0] for call in closed.call_args_list],
            [33, 32, 31, 30],
        )


class SourceAuthorityResolverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.run = Path(self.temporary.name) / "run"

    def tearDown(self):
        self.temporary.cleanup()

    def host_frontier(self):
        return {
            "source_authority_registry_origin": custody.HOST_SYSTEM_SOURCE_AUTHORITY_ORIGIN,
            "source_authority_registry": REGISTRY.to_record(),
            "source_authority_registry_sha256": REGISTRY.digest,
        }

    def test_host_origin_revalidates_only_fixed_host_root(self):
        with patch.object(
                custody, "read_host_system_source_authority_registry",
                return_value=REGISTRY):
            self.assertIs(
                custody.resolve_source_authority_registry(self.run, self.host_frontier()),
                REGISTRY)
        with patch.object(
                custody, "read_host_system_source_authority_registry",
                return_value=Mock(digest="f" * 64)), \
                self.assertRaises(BilqisError) as caught:
            custody.resolve_source_authority_registry(self.run, self.host_frontier())
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH",
        )

    def test_legacy_origin_absence_uses_run_local_root(self):
        provision_source_authority_registry(self.run, REGISTRY)
        frontier = with_source_authority_registry(
            candidate(parent_state()), REGISTRY).correction_frontier
        self.assertEqual(
            custody.resolve_source_authority_registry(self.run, frontier), REGISTRY)

    def test_historical_unanchored_returns_none_and_explicit_null_rejects(self):
        self.assertIsNone(custody.resolve_source_authority_registry(self.run, {}))
        with self.assertRaises(BilqisError) as caught:
            custody.resolve_source_authority_registry(
                self.run, {"source_authority_registry_origin": None})
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID",
        )

    def test_successor_host_is_exact_and_cannot_downgrade(self):
        parent = self.host_frontier()
        with patch.object(
                custody, "read_host_system_source_authority_registry",
                return_value=REGISTRY):
            self.assertIs(
                custody.require_source_authority_successor_inheritance(
                    self.run, parent, dict(parent), allow_historical_anchor=False),
                REGISTRY)
        with self.assertRaises(BilqisError) as caught:
            custody.require_source_authority_successor_inheritance(
                self.run, parent, {}, allow_historical_anchor=False)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID",
        )

    def test_historical_anchor_is_explicitly_permissioned(self):
        provision_source_authority_registry(self.run, REGISTRY)
        candidate_frontier = {
            "source_authority_registry": REGISTRY.to_record(),
            "source_authority_registry_sha256": REGISTRY.digest,
        }
        with self.assertRaises(BilqisError) as caught:
            custody.require_source_authority_successor_inheritance(
                self.run, {}, candidate_frontier, allow_historical_anchor=False)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID",
        )
        self.assertEqual(
            custody.require_source_authority_successor_inheritance(
                self.run, {}, candidate_frontier, allow_historical_anchor=True),
            REGISTRY)


if __name__ == "__main__":
    unittest.main()
