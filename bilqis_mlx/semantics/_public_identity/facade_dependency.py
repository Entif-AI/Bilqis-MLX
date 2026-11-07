"""Resolve historical public-facade dependencies at call time."""
from __future__ import annotations

from importlib import import_module
from types import ModuleType


def public_facade(module_name: str) -> ModuleType:
    """Return the live public facade so patched dependency hooks stay authoritative."""
    return import_module(module_name)
