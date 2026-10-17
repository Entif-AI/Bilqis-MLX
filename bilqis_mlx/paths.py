"""Single source of truth for repository-local runtime inputs and storage.

Training never needs the former Bilqis checkout beside this repository.
The optional data-root override is deliberate user configuration, not an
implicit source-code dependency or a checkout-relative search path.
"""
from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE = REPO_ROOT / "vendor" / "legacy-v16"
LEGACY_CHECKPOINTS = LEGACY_SOURCE / "runs" / "primitive-consolidation-v16-triplets"


def storage_root() -> Path:
    configured = os.environ.get("BILQIS_STORAGE_ROOT", "").strip()
    if not configured:
        return REPO_ROOT / "runs"
    location = Path(configured).expanduser()
    return (location if location.is_absolute() else REPO_ROOT / location).resolve()


def active_run_dir() -> Path:
    return storage_root() / "school-mlx-v1"
