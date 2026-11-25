"""Instrument a callable at its actual consuming global binding."""
from __future__ import annotations

from dataclasses import dataclass, field
import dis
from functools import wraps
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

from .imports import resolve_module, resolve_source, validate_loaded


@dataclass
class _Probe:
    module: object
    definition: object
    namespace: dict
    consumer: str
    binding: str
    original: object
    wrapper: object
    label: str
    samples: list[float] = field(default_factory=list)


class ProbeBook:
    """Install timing at a named consumer's global lookup; require real calls."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._probes: list[_Probe] = []

    def bind(self, owner: str | Path, consumer_name: str, binding: str, *, label=None):
        module = (resolve_source(owner, self.root) if isinstance(owner, Path)
                  else resolve_module(owner, self.root))
        module_name = module.__name__
        namespace = vars(module)
        original = namespace.get(binding)
        if not callable(original):
            raise ValueError(f"missing callable binding {module_name}.{binding}")
        definition = sys.modules.get(getattr(original, "__module__", ""))
        if definition is not None and not definition.__name__.startswith("bilqis_mlx."):
            definition = None
        consumer = namespace.get(consumer_name)
        if getattr(consumer, "__globals__", None) is not namespace:
            raise ValueError(f"missing local consumer {module_name}.{consumer_name}")
        code = consumer.__code__
        if not any(item.opname.startswith("LOAD_GLOBAL") and item.argval == binding
                   for item in dis.get_instructions(code)):
            raise ValueError(f"{module_name}.{consumer_name} does not load {binding}")
        name = label or f"{module_name}.{consumer_name}:{binding}"
        if any(p.label == name or (p.namespace is namespace and p.binding == binding)
               for p in self._probes):
            raise ValueError(f"duplicate probe binding or label: {name}")
        samples = []

        @wraps(original)
        def wrapper(*args, **kwargs):
            if sys._getframe(1).f_code is not code:
                return original(*args, **kwargs)
            started = perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                samples.append(perf_counter() - started)

        namespace[binding] = wrapper
        self._probes.append(_Probe(module, definition, namespace, consumer_name, binding, original,
                                   wrapper, name, samples))
        return samples

    def contract_sha256(self):
        """Bind the prepared consumer/definition identities, not timing values."""
        records = sorted(
            (p.label, p.module.__name__, p.consumer, p.binding,
             p.definition.__name__ if p.definition is not None else "")
            for p in self._probes)
        return hashlib.sha256(json.dumps(records, separators=(",", ":")).encode()).hexdigest()

    def verify(self):
        validate_loaded(self.root, tuple(
            owner for probe in self._probes for owner in (probe.module, probe.definition)
            if owner is not None))
        for probe in self._probes:
            if probe.namespace.get(probe.binding) is not probe.wrapper:
                raise RuntimeError(f"probe binding replaced: {probe.label}")

    def reset(self):
        for probe in self._probes:
            probe.samples.clear()

    def require_calls(self):
        self.verify()
        missing = [p.label for p in self._probes if not p.samples]
        if missing:
            raise RuntimeError(f"required probes have no observed calls: {', '.join(missing)}")

    def results(self):
        return {p.label: {"calls": len(p.samples), "seconds": sum(p.samples)}
                for p in self._probes}

    def restore(self):
        for probe in reversed(self._probes):
            if probe.namespace.get(probe.binding) is probe.wrapper:
                probe.namespace[probe.binding] = probe.original
        self._probes.clear()
