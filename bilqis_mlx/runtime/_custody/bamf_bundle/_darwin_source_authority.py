"""Darwin descriptor boundary for the fixed C09 host trust root."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import errno
import os
import stat

from .records import invalid


ACL_TYPE_EXTENDED = 0x00000100
ACL_FIRST_ENTRY = 0
ACL_NEXT_ENTRY = -1
ACL_EXTENDED_ALLOW = 1
ACL_EXTENDED_DENY = 2
ID_TYPE_UID = 0
ID_TYPE_GID = 1

_PERMISSIONS = {
    "ACL_WRITE_DATA": 1 << 2,
    "ACL_DELETE": 1 << 4,
    "ACL_APPEND_DATA": 1 << 5,
    "ACL_DELETE_CHILD": 1 << 6,
    "ACL_WRITE_ATTRIBUTES": 1 << 8,
    "ACL_WRITE_EXTATTRIBUTES": 1 << 10,
    "ACL_WRITE_SECURITY": 1 << 12,
    "ACL_CHANGE_OWNER": 1 << 13,
}
_MUTATION_PERMISSIONS = frozenset(_PERMISSIONS)
_INVALID = "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID"
_REQUIRED = "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED"


@dataclass(frozen=True)
class DarwinAclEntry:
    tag: int
    principal_kind: str
    principal_id: int
    permissions: frozenset[str]


def _fail(reason=_INVALID):
    invalid(reason)


def _libsystem():
    try:
        library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        library.acl_get_fd_np.argtypes = [ctypes.c_int, ctypes.c_int]
        library.acl_get_fd_np.restype = ctypes.c_void_p
        library.acl_get_entry.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        library.acl_get_entry.restype = ctypes.c_int
        library.acl_get_tag_type.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        library.acl_get_tag_type.restype = ctypes.c_int
        library.acl_get_qualifier.argtypes = [ctypes.c_void_p]
        library.acl_get_qualifier.restype = ctypes.c_void_p
        library.acl_get_permset.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        library.acl_get_permset.restype = ctypes.c_int
        library.acl_get_perm_np.argtypes = [ctypes.c_void_p, ctypes.c_int]
        library.acl_get_perm_np.restype = ctypes.c_int
        library.acl_free.argtypes = [ctypes.c_void_p]
        library.acl_free.restype = ctypes.c_int
        library.mbr_uuid_to_id.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_int)]
        library.mbr_uuid_to_id.restype = ctypes.c_int
        return library
    except (AttributeError, OSError):
        _fail()


def _acl_entry(library, raw_entry) -> DarwinAclEntry:
    tag = ctypes.c_int()
    if library.acl_get_tag_type(raw_entry, ctypes.byref(tag)) != 0:
        _fail()
    if tag.value not in {ACL_EXTENDED_ALLOW, ACL_EXTENDED_DENY}:
        _fail()
    qualifier = library.acl_get_qualifier(raw_entry)
    if not qualifier:
        _fail()
    try:
        principal = ctypes.c_uint32()
        principal_type = ctypes.c_int()
        if library.mbr_uuid_to_id(
                qualifier, ctypes.byref(principal), ctypes.byref(principal_type)) != 0:
            _fail()
        if principal_type.value not in {ID_TYPE_UID, ID_TYPE_GID}:
            _fail()
    finally:
        library.acl_free(qualifier)
    permset = ctypes.c_void_p()
    if library.acl_get_permset(raw_entry, ctypes.byref(permset)) != 0 or not permset:
        _fail()
    present = []
    for name, permission in _PERMISSIONS.items():
        result = library.acl_get_perm_np(permset, permission)
        if result < 0:
            _fail()
        if result == 1:
            present.append(name)
    return DarwinAclEntry(
        tag.value,
        "UID" if principal_type.value == ID_TYPE_UID else "GID",
        principal.value,
        frozenset(present),
    )


def read_extended_acl(fd: int) -> tuple[DarwinAclEntry, ...]:
    """Read one Darwin extended ACL, failing closed on every ambiguous result."""
    library = _libsystem()
    ctypes.set_errno(0)
    acl = library.acl_get_fd_np(fd, ACL_TYPE_EXTENDED)
    if not acl:
        if ctypes.get_errno() == errno.ENOENT:
            return ()
        _fail()
    entries = []
    try:
        entry_id = ACL_FIRST_ENTRY
        while True:
            raw_entry = ctypes.c_void_p()
            ctypes.set_errno(0)
            result = library.acl_get_entry(acl, entry_id, ctypes.byref(raw_entry))
            if result == -1:
                if entry_id == ACL_NEXT_ENTRY and entries and ctypes.get_errno() == errno.EINVAL:
                    break
                _fail()
            if result != 0 or not raw_entry:
                _fail()
            entries.append(_acl_entry(library, raw_entry))
            entry_id = ACL_NEXT_ENTRY
    finally:
        library.acl_free(acl)
    return tuple(entries)


def require_safe_host_descriptor(fd: int, *, directory: bool) -> os.stat_result:
    """Require a root-owned non-writable descriptor without mutating ACL grants."""
    try:
        info = os.fstat(fd)
    except OSError:
        _fail()
    expected = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if (not expected or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
        _fail()
    for entry in read_extended_acl(fd):
        if (entry.tag == ACL_EXTENDED_ALLOW
                and entry.permissions & _MUTATION_PERMISSIONS
                and (entry.principal_kind != "UID" or entry.principal_id != 0)):
            _fail()
    return info


def _open_component(parent_fd: int, name: str, *, directory: bool, required: bool) -> int:
    flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if directory else 0)
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        if required and error.errno == errno.ENOENT:
            _fail(_REQUIRED)
        _fail()


def open_host_source_authority_registry_fd(*, max_bytes: int) -> int:
    """Open the fixed Darwin host registry through verified root-owned descriptors."""
    if type(max_bytes) is not int or max_bytes <= 0:
        _fail()
    try:
        etc_link = os.lstat("/etc")
        if (not stat.S_ISLNK(etc_link.st_mode) or etc_link.st_uid != 0
                or os.readlink("/etc") != "private/etc"):
            _fail()
        etc_target = os.stat("/etc")
        root_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        _fail()
    opened = [root_fd]
    final_fd = None
    try:
        require_safe_host_descriptor(root_fd, directory=True)
        parent = root_fd
        for name, required in (("private", False), ("etc", False),
                               ("entif-ai", True), ("bilqis", True)):
            child = _open_component(parent, name, directory=True, required=required)
            opened.append(child)
            require_safe_host_descriptor(child, directory=True)
            parent = child
            if name == "etc":
                physical = os.fstat(child)
                if (physical.st_dev, physical.st_ino) != (etc_target.st_dev, etc_target.st_ino):
                    _fail()
        final_fd = _open_component(
            parent, "source-authority-registry.json", directory=False, required=True)
        info = require_safe_host_descriptor(final_fd, directory=False)
        if not 1 <= info.st_size <= max_bytes:
            _fail()
        return final_fd
    except BaseException:
        if final_fd is not None:
            os.close(final_fd)
        raise
    finally:
        for fd in reversed(opened):
            os.close(fd)

