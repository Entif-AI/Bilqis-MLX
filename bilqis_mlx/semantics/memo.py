"""Process-local memoization of pure source results, never neural predictions."""
from __future__ import annotations

from functools import wraps
from inspect import signature
from threading import RLock

from .domains import contract_digest


class PureOperationMemo:
    """Explicit solver-owned cache; no evaluator/oracle state is shared."""

    def __init__(self) -> None:
        self._values: dict[str, object] = {}
        self._lock = RLock()

    @staticmethod
    def key(
        *, operator: object, dependencies: tuple, authority: object,
    ) -> str:
        # Only consulted source, predecessor, rights and operator identities.
        return contract_digest({
            "schema": "bilqis.cognitive-pure-memo-key/v1",
            "operator": operator,
            "dependencies": dependencies,
            "authority": authority,
        })

    def get(self, key: str) -> object | None:
        with self._lock:
            return self._values.get(key)

    def put(self, key: str, value: object) -> None:
        with self._lock:
            self._values[key] = value


def memoize_source(*, semantics):
    """Hash typed arguments and semantic contracts in an evaluator-owned cache.

    Each wrapped source or independent oracle owns separate entries. Inputs
    contain expression structure, types, operator contracts and world bindings;
    checkpoint identity, student answers and display strings are not required.
    Only successful immutable source results belong here. Entries survive
    checkpoint changes within this process and are discarded on process exit.
    """
    def decorate(function):
        binding = signature(function)
        namespace = (function.__module__, function.__qualname__, semantics)
        results = {}
        lock = RLock()

        @wraps(function)
        def evaluate(*args, **kwargs):
            inputs = binding.bind(*args, **kwargs)
            inputs.apply_defaults()
            key = contract_digest((namespace, inputs.arguments))
            with lock:
                if key not in results:
                    results[key] = function(*args, **kwargs)
                return results[key]

        def clear():
            with lock:
                results.clear()

        evaluate.cache_clear = clear
        return evaluate

    return decorate
