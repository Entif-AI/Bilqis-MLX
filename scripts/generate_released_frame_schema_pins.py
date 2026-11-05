"""Compatibility entrypoint for the canonical BAMF A03 source-pin generator.

The implementation lives in ``scripts/bamf/generate_released_frame_schema_pins.py``.
Keep this historical path as a thin launcher so there is exactly one publication
authority and both supported CLI paths produce identical artifacts.
"""
from __future__ import annotations

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "bamf" /
            "generate_released_frame_schema_pins.py"),
        run_name="__main__",
    )
