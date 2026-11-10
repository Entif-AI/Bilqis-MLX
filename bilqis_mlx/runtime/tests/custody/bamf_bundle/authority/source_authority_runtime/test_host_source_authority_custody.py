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
        self.assertEqual(entries[1].tag, "DENY")

    def test_descriptor_rejects_non_root_mode_and_mutating_allow(self):
        safe = _info()
        dangerous = darwin.DarwinAclEntry(
            "ALLOW", "UID", 501,
            frozenset({"ACL_WRITE_SECURITY"}))
        for info, acl in (
            (_info(uid=501), ()),
            (_info(mode=0o620), ()),
            (safe, (dangerous,)),
            (safe, (darwin.DarwinAclEntry(
                "ALLOW", "GID", 0,
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
                "ALLOW", "UID", 501,
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
            darwin.DarwinAclEntry("ALLOW", "UID", 501, frozenset()),
            darwin.DarwinAclEntry(
                "ALLOW", "UID", 0,
                frozenset({"ACL_DELETE_CHILD"})),
        )
        info = _info()
        with patch.object(darwin.os, "fstat", return_value=info), \
                patch.object(darwin, "read_extended_acl", return_value=acl):
            self.assertIs(darwin.require_safe_host_descriptor(7, directory=False), info)

if __name__ == "__main__":
    unittest.main()
