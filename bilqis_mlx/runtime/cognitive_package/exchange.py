"""Create-only local package transport; compatibility staging grants no activation."""
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import stat
import tempfile

from .contracts import PackageBinding, digest_string, require
from .records import CognitivePackage, ImportPlan
from .staging import stage_import


@dataclass(frozen=True)
class StagedExchange:
    package: CognitivePackage
    plan: ImportPlan
    path: Path


def _directory(path):
    path = Path(path)
    require(not path.is_symlink() and (not path.exists() or path.is_dir()),
            'package directory must be a regular directory')
    return path


def _read_regular(path, limit):
    require(not path.is_symlink() and path.is_file(), 'package entry must be regular')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        require(stat.S_ISREG(os.fstat(source.fileno()).st_mode),
                'package entry must be regular')
        raw = source.read(limit + 1)
    require(len(raw) <= limit, 'package exceeds wire limit')
    return raw


def _sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_package(package, directory):
    """Validate before publication; retries never replace an existing entry."""
    require(type(package) is CognitivePackage, 'invalid cognitive package')
    raw = package.canonical_json.encode('utf-8')
    directory = _directory(directory)
    destination = directory / (sha256(raw).hexdigest() + '.json')
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix='.package-', delete=False) as target:
            temporary = Path(target.name)
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            require(_read_regular(destination, len(raw)) == raw,
                    'package destination conflict')
        _sync_directory(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def receive_package(sender, receiver, package_digest, binding, *, max_wire_bytes):
    """Copy only validated compatible bytes into a receiver's staging directory."""
    require(digest_string(package_digest), 'invalid package digest')
    require(type(max_wire_bytes) is int and max_wire_bytes > 0,
            'invalid package wire limit')
    require(type(binding) is PackageBinding, 'invalid receiver binding')
    binding.__post_init__()
    sender = _directory(sender)
    raw = _read_regular(sender / (package_digest + '.json'), max_wire_bytes)
    require(sha256(raw).hexdigest() == package_digest, 'package wire digest mismatch')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        require(False, 'invalid package wire encoding')
    package = CognitivePackage.from_canonical_json(text)
    plan = stage_import(package, binding)
    path = publish_package(package, receiver)
    return StagedExchange(package, plan, path)
