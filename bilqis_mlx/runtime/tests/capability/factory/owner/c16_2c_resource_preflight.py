"""ADR-138 host-resource gate for C16.2c detached MLX witnesses."""
from __future__ import annotations

import os
import re
import subprocess

MIN_MEMORY_FREE_PERCENT = 20


def _checked(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"C16_2C_RESOURCE_PREFLIGHT_FAILED command={command!r}")
    return result.stdout


def require_mlx_verification_resources():
    """Fail before expensive setup when ADR-138 launch conditions are unsafe."""
    if os.environ.get("BILQIS_TEST_WORKERS") != "1":
        raise RuntimeError("C16_2C_MLX_WORKERS_UNSAFE expected=1")

    memory = _checked(["memory_pressure", "-Q"])
    match = re.search(r"memory free percentage:\s*(\d+)%", memory)
    if not match:
        raise RuntimeError("C16_2C_MLX_MEMORY_PRESSURE_UNREADABLE")
    memory_free = int(match.group(1))
    if memory_free < MIN_MEMORY_FREE_PERCENT:
        raise RuntimeError(
            f"C16_2C_MLX_MEMORY_PRESSURE free_percent={memory_free}")

    swap = _checked(["sysctl", "vm.swapusage"])
    match = re.search(
        r"total\s*=\s*([0-9.]+)M.*free\s*=\s*([0-9.]+)M", swap)
    if not match:
        raise RuntimeError("C16_2C_MLX_SWAP_UNREADABLE")
    total_mib, free_mib = (float(value) for value in match.groups())
    swap_free_fraction = 1.0 if total_mib == 0 else free_mib / total_mib
    return {
        "test_workers": 1,
        "memory_free_percent": memory_free,
        "swap_free_fraction": swap_free_fraction,
    }


__all__ = ("require_mlx_verification_resources",)
