"""Bounded ordinary-mode HOW projection; the authenticated journal owns truth."""
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from threading import RLock

from bilqis_mlx.runtime.state import _fingerprint
from .replay_fold import PORTABLE_TEACHER_AUTHORITY

_MAX_REPLAY_SNAPSHOTS = 4


@dataclass
class _Snapshot:
    receipts: tuple = ()
    teacher: dict | None = None
    lock: object = field(default_factory=RLock, repr=False)

    def replay(self, base, rows, fold):
        receipts = tuple(receipt for _, _, _, receipt, _ in rows)
        with self.lock:
            prefix = len(self.receipts)
            if self.teacher is not None and receipts[:prefix] == self.receipts:
                result = fold(deepcopy(self.teacher), rows[prefix:])
            else:
                result = fold(base, rows)
            self.teacher = deepcopy(result)
            self.receipts = receipts
            return result


@lru_cache(maxsize=_MAX_REPLAY_SNAPSHOTS)
def _snapshot(_binding):
    return _Snapshot()


def replay_ordinary(run_dir, cache, teacher, rows, fold):
    """Reuse only an exact authenticated prefix of compact ordinary outcomes.

    Strict/historical candidate evidence is deliberately replayed in full.
    A shortened, reordered or replaced receipt sequence rebuilds from base.
    The caller never receives the cached mutable teacher object.
    """
    if not rows or any(
            evidence.get(PORTABLE_TEACHER_AUTHORITY) is not True
            or evidence.get("candidate_evidence") is not None
            for _, _, _, _, evidence in rows):
        return fold(teacher, rows)
    binding = (
        str(Path(run_dir).absolute()), cache.generation,
        cache.accepted_manifest_sha256, _fingerprint(teacher),
    )
    return _snapshot(binding).replay(teacher, rows, fold)
