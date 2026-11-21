"""Dedicated data-plane custody for B13 accepted-authority checkpoints and tips."""
from __future__ import annotations

import hashlib
import sqlite3

from .contracts import DataPlaneError


_CHECKPOINT_PAYLOAD_INDEX = 4


class DataPlaneAcceptedAuthorityMixin:
    """Private persistence API consumed only by the B13 accepted-authority owner."""

    def _store_accepted_authority_checkpoint(
            self, checkpoint_sha256: str, run_id: str, generation: int,
            manifest_sha256: str, parent_checkpoint_sha256: str | None,
            raw: bytes) -> None:
        if (not isinstance(run_id, str) or not run_id
                or type(generation) is not int or generation < 0
                or not isinstance(manifest_sha256, str)
                or hashlib.sha256(raw).hexdigest() != checkpoint_sha256):
            raise ValueError(DataPlaneError.ACCEPTED_AUTHORITY_CHECKPOINT_INVALID.value)
        with self.transaction():
            existing = self._db.execute(
                "SELECT run_id,generation,manifest_sha256,parent_checkpoint_sha256,payload "
                "FROM bamf_accepted_authority_checkpoints WHERE checkpoint_sha256=?",
                (checkpoint_sha256,),
            ).fetchone()
            expected = (
                run_id, generation, manifest_sha256, parent_checkpoint_sha256, raw,
            )
            if existing is not None:
                if existing != expected:
                    raise ValueError(
                        DataPlaneError.ACCEPTED_AUTHORITY_CHECKPOINT_CORRUPTED.value)
                return
            try:
                self._db.execute(
                    "INSERT INTO bamf_accepted_authority_checkpoints("
                    "checkpoint_sha256,run_id,generation,manifest_sha256,"
                    "parent_checkpoint_sha256,payload) VALUES(?,?,?,?,?,?)",
                    (checkpoint_sha256, run_id, generation, manifest_sha256,
                     parent_checkpoint_sha256, raw),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    DataPlaneError.ACCEPTED_AUTHORITY_CHECKPOINT_INVALID.value) from error

    def _accepted_authority_checkpoint(self, checkpoint_sha256: str):
        with self._lock:
            row = self._db.execute(
                "SELECT run_id,generation,manifest_sha256,parent_checkpoint_sha256,payload "
                "FROM bamf_accepted_authority_checkpoints WHERE checkpoint_sha256=?",
                (checkpoint_sha256,),
            ).fetchone()
        if row is None:
            return None
        if hashlib.sha256(row[_CHECKPOINT_PAYLOAD_INDEX]).hexdigest() != checkpoint_sha256:
            raise ValueError(DataPlaneError.ACCEPTED_AUTHORITY_CHECKPOINT_CORRUPTED.value)
        return row

    def _accepted_authority_checkpoint_for_manifest(
            self, run_id: str, manifest_sha256: str):
        with self._lock:
            row = self._db.execute(
                "SELECT checkpoint_sha256,generation,parent_checkpoint_sha256,payload "
                "FROM bamf_accepted_authority_checkpoints "
                "WHERE run_id=? AND manifest_sha256=?",
                (run_id, manifest_sha256),
            ).fetchone()
        if row is None:
            return None
        checkpoint_sha256, generation, parent_checkpoint_sha256, raw = row
        if hashlib.sha256(raw).hexdigest() != checkpoint_sha256:
            raise ValueError(DataPlaneError.ACCEPTED_AUTHORITY_CHECKPOINT_CORRUPTED.value)
        return checkpoint_sha256, generation, parent_checkpoint_sha256, raw

    def _accepted_authority_tip(self, run_id: str):
        with self._lock:
            return self._db.execute(
                "SELECT checkpoint_sha256,generation "
                "FROM bamf_accepted_authority_tips WHERE run_id=?",
                (run_id,),
            ).fetchone()

    def _compare_and_swap_accepted_authority_tip(
            self, run_id: str, expected_checkpoint_sha256: str | None,
            new_checkpoint_sha256: str) -> None:
        with self.transaction():
            checkpoint = self._db.execute(
                "SELECT run_id,generation,parent_checkpoint_sha256 "
                "FROM bamf_accepted_authority_checkpoints WHERE checkpoint_sha256=?",
                (new_checkpoint_sha256,),
            ).fetchone()
            if checkpoint is None or checkpoint[0] != run_id:
                raise ValueError(DataPlaneError.ACCEPTED_AUTHORITY_TIP_INVALID.value)
            _, new_generation, parent_checkpoint_sha256 = checkpoint
            current = self._db.execute(
                "SELECT checkpoint_sha256,generation "
                "FROM bamf_accepted_authority_tips WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if current is not None and current[0] == new_checkpoint_sha256:
                if current[1] != new_generation:
                    raise ValueError(DataPlaneError.ACCEPTED_AUTHORITY_TIP_INVALID.value)
                return
            if expected_checkpoint_sha256 is None:
                if current is not None or parent_checkpoint_sha256 is not None:
                    raise ValueError(DataPlaneError.ACCEPTED_AUTHORITY_TIP_CONFLICT.value)
                self._db.execute(
                    "INSERT INTO bamf_accepted_authority_tips("
                    "run_id,generation,checkpoint_sha256) VALUES(?,?,?)",
                    (run_id, new_generation, new_checkpoint_sha256),
                )
                return
            if (current is None or current[0] != expected_checkpoint_sha256
                    or parent_checkpoint_sha256 != expected_checkpoint_sha256
                    or new_generation != current[1] + 1):
                raise ValueError(DataPlaneError.ACCEPTED_AUTHORITY_TIP_CONFLICT.value)
            updated = self._db.execute(
                "UPDATE bamf_accepted_authority_tips "
                "SET generation=?,checkpoint_sha256=? "
                "WHERE run_id=? AND generation=? AND checkpoint_sha256=?",
                (new_generation, new_checkpoint_sha256, run_id,
                 current[1], expected_checkpoint_sha256),
            )
            if updated.rowcount != 1:
                raise ValueError(DataPlaneError.ACCEPTED_AUTHORITY_TIP_CONFLICT.value)


__all__ = ("DataPlaneAcceptedAuthorityMixin",)
