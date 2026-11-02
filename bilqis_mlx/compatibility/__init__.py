"""Stable public compatibility module paths over compartmentalized implementations."""
from importlib import import_module
import sys

_LEGACY_MODULES = (
    "identities", "source_adapter_resume", "telemetry_events",
    "resume_migration", "factory_release_v1", "source_adapters",
    "source_bootstrap",
)
for _name in _LEGACY_MODULES:
    sys.modules[f"{__name__}.{_name}"] = import_module(f".legacy.{_name}", __name__)
del _name
