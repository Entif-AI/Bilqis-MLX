"""Repository-owned bootstrap inputs for a fresh local BAMF lineage."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_RUN = ROOT / "source-run"
ATLAS_ROOT = ROOT / "atlas"
ATLAS_BUNDLE_ID = "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
ATLAS_RELEASE_SHA256 = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
ATLAS_SOURCE_BUNDLE_ID = "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec"
ATLAS_MANIFEST = ATLAS_ROOT / ATLAS_BUNDLE_ID / "manifest.json"


__all__ = (
    "ATLAS_BUNDLE_ID",
    "ATLAS_MANIFEST",
    "ATLAS_RELEASE_SHA256",
    "ATLAS_ROOT",
    "ATLAS_SOURCE_BUNDLE_ID",
    "ROOT",
    "SOURCE_RUN",
)
