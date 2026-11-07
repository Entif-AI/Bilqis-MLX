"""Durable signed C09 correction stream for one accepted BAMF generation."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
from threading import RLock
from typing import Callable

from bilqis_mlx.data_plane import data_plane

from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import CorrectionEvent
from .atlas_source_authority import SourceAuthorityRegistry
from bilqis_mlx.runtime.capability_support_journal import (
    _event_record, event_from_record,
)


_LEDGER_EVENT = "BAMF_C09_CORRECTION"
_RUNTIME_LOCK = RLock()


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _ledger_record(manifest_sha256: str, event: CorrectionEvent) -> dict:
    body = {
        "event": _LEDGER_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "correction": _event_record(event),
    }
    return {
        "event_id": hashlib.sha256(_canonical(body)).hexdigest(),
        **body,
    }


def accepted_correction_id(
    manifest_sha256: str, event: CorrectionEvent,
) -> str:
    return _ledger_record(manifest_sha256, event)["event_id"]


def _read_records(run_dir: Path, manifest_sha256: str) -> tuple[dict, ...]:
    path = Path(run_dir) / "events.jsonl"
    if not path.exists():
        return ()
    if path.is_symlink() or not path.is_file():
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    records = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.endswith("\n"):
                    _invalid("BAMF_C09_CORRECTION_LEDGER_TRUNCATED")
                item = json.loads(line)
                if (not isinstance(item, dict)
                        or item.get("event") != _LEDGER_EVENT
                        or item.get("accepted_manifest_sha256")
                        != manifest_sha256):
                    continue
                body = {key: value for key, value in item.items()
                        if key != "event_id"}
                if item.get("event_id") != hashlib.sha256(
                        _canonical(body)).hexdigest():
                    _invalid("BAMF_C09_CORRECTION_LEDGER_DRIFT")
                records.append(item)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    by_id = {}
    ordered = []
    for item in records:
        event_id = item["event_id"]
        prior = by_id.get(event_id)
        if prior is not None and prior != item:
            _invalid("BAMF_C09_CORRECTION_LEDGER_CONFLICT")
        if prior is None:
            by_id[event_id] = item
            ordered.append(item)
    return tuple(ordered)


def accepted_corrections(
    run_dir: Path, manifest_sha256: str,
    registry: SourceAuthorityRegistry | None,
) -> tuple[tuple[str, CorrectionEvent], ...]:
    records = _read_records(run_dir, manifest_sha256)
    if records and not isinstance(registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
    result = []
    for item in records:
        event = event_from_record(item["correction"])
        registry.verify_correction(event)
        result.append((item["event_id"], event))
    return tuple(result)


@dataclass
class _Target:
    apply: Callable[[CorrectionEvent, SourceAuthorityRegistry], object]
    seen: set[str] = field(default_factory=set)


class _AcceptedCorrectionRuntime:
    def __init__(self, run_dir: Path, manifest_sha256: str):
        self.run_dir = Path(run_dir)
        self.manifest_sha256 = manifest_sha256
        self.registry: SourceAuthorityRegistry | None = None
        self.targets: dict[tuple[str, int], _Target] = {}
        self.lock = RLock()

    def bind_registry(self, registry: SourceAuthorityRegistry | None) -> None:
        if registry is None:
            return
        if not isinstance(registry, SourceAuthorityRegistry):
            _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
        if self.registry is not None and self.registry != registry:
            _invalid("BAMF_C09_CORRECTION_AUTHORITY_DRIFT")
        self.registry = registry

    def register(
        self, kind: str, owner, apply,
        registry: SourceAuthorityRegistry | None,
        seen_event_ids: tuple[str, ...] = (),
    ) -> None:
        with self.lock:
            self.bind_registry(registry)
            key = (kind, id(owner))
            target = self.targets.setdefault(key, _Target(apply))
            target.seen.update(seen_event_ids)
            for event_id, event in accepted_corrections(
                    self.run_dir, self.manifest_sha256, self.registry):
                if event_id in target.seen:
                    continue
                target.apply(event, self.registry)
                target.seen.add(event_id)

    def deliver(self, event_id: str, event: CorrectionEvent,
                registry: SourceAuthorityRegistry) -> None:
        with self.lock:
            self.bind_registry(registry)
            for target in self.targets.values():
                if event_id in target.seen:
                    continue
                target.apply(event, self.registry)
                target.seen.add(event_id)


class _CorrectionRuntimeOwner:
    """Process-lifetime registry for accepted correction runtimes."""

    def __init__(self):
        self.entries = {}

    def get(self, key):
        return self.entries.get(key)

    def set(self, key, runtime) -> None:
        self.entries[key] = runtime

    def clear(self) -> None:
        self.entries.clear()


_RUNTIME_OWNER = _CorrectionRuntimeOwner()


def _runtime(run_dir: Path, manifest_sha256: str) -> _AcceptedCorrectionRuntime:
    key = (str(Path(run_dir).resolve()), manifest_sha256)
    with _RUNTIME_LOCK:
        runtime = _RUNTIME_OWNER.get(key)
        if runtime is None:
            runtime = _AcceptedCorrectionRuntime(Path(run_dir), manifest_sha256)
            _RUNTIME_OWNER.set(key, runtime)
        return runtime


def register_accepted_target(
    run_dir: Path, manifest_sha256: str, kind: str, owner, apply,
    registry: SourceAuthorityRegistry | None = None,
    seen_event_ids: tuple[str, ...] = (),
) -> None:
    _runtime(run_dir, manifest_sha256).register(
        kind, owner, apply, registry, seen_event_ids)


def bind_accepted_registry(
    run_dir: Path, manifest_sha256: str, registry: SourceAuthorityRegistry,
) -> None:
    runtime = _runtime(run_dir, manifest_sha256)
    with runtime.lock:
        runtime.bind_registry(registry)


def register_compiled_batch(
    run_dir: Path, batch, registry: SourceAuthorityRegistry | None = None,
) -> None:
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
    from .owners.atlas_owner_ingress import apply_compiled_batch_correction

    cache = bind_accepted_execution_cache(run_dir)
    register_accepted_target(
        run_dir, cache.accepted_manifest_sha256, "B11_BATCH", batch,
        lambda event, authority: apply_compiled_batch_correction(
            batch, event, authority),
        registry,
    )


def register_solve_context(
    run_dir: Path, context, registry: SourceAuthorityRegistry | None = None,
) -> None:
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
    from .owners.atlas_owner_ingress import apply_solve_context_correction

    cache = bind_accepted_execution_cache(run_dir)
    register_accepted_target(
        run_dir, cache.accepted_manifest_sha256, "C04_CONTEXT", context,
        lambda event, authority: apply_solve_context_correction(
            context, event, authority),
        registry,
    )


def record_accepted_correction(
    run_dir: Path, event: CorrectionEvent,
    registry: SourceAuthorityRegistry,
) -> str:
    """Persist and synchronously deliver one signed correction to live owners."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

    if not isinstance(event, CorrectionEvent):
        _invalid("BAMF_C09_CORRECTION_EVENT_REQUIRED")
    registry.verify_correction(event)
    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    record = _ledger_record(cache.accepted_manifest_sha256, event)
    prior = _read_records(run_dir, cache.accepted_manifest_sha256)
    if all(item["event_id"] != record["event_id"] for item in prior):
        path = run_dir / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = _canonical(record) + b"\n"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, raw)
            os.fsync(fd)
        finally:
            os.close(fd)
        data_plane().sync_event_ledger(run_dir)
    runtime = _runtime(run_dir, cache.accepted_manifest_sha256)
    runtime.deliver(record["event_id"], event, registry)
    object.__setattr__(cache, "_correction_registry", registry)
    return record["event_id"]


__all__ = (
    "accepted_correction_id", "accepted_corrections", "bind_accepted_registry",
    "record_accepted_correction", "register_accepted_target",
    "register_compiled_batch", "register_solve_context",
)
