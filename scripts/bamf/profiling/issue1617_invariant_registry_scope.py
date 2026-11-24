"""Disposable #1617 experiment; never import this from production runtime.

The detached launcher pins the entire source tree. Reuse only in an ordinary
call entered with the same admitted SourceExecutionContext. Strict calls and
unowned calls always execute the reference functions. No row, gold, plan,
prediction, or optimizer state is memoized.
"""
from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from functools import wraps
import sys


class PreparedOwner:
    def __init__(self, context):
        self.context = context
        self.release = context.release
        self.graph = context.graph
        self.source_root = context.source_root
        self.source_registry = context.source_registry
        self.registries = {}
        self.implementation_digests = {}
        self.lowerers = None
        self.canonical_registry = None

    def matches(self, context):
        return (self.context is context
                and self.release is context.release
                and self.graph is context.graph
                and self.source_root == context.source_root
                and self.source_registry is context.source_registry)


def install_scope():
    """Patch actual function aliases for one disposable worker, after profiling.

    This is deliberately not a live-runtime invalidation contract. In particular,
    the detached immutable source snapshot is an experimental precondition.
    """
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    from bilqis_mlx.semantics.cognitive_operators import registry
    from bilqis_mlx.source_adapters import school
    from bilqis_mlx.source_adapters import task_goal_registry

    active = ContextVar('issue1617_active_owner', default=None)
    counts = Counter()
    latest = None

    def owned():
        return None if strict_evidence_enabled() else active.get()

    def around(fn):
        @wraps(fn)
        def call(context, *args, **kwargs):
            nonlocal latest
            if (strict_evidence_enabled()
                    or getattr(context, '_accepted_feature_context', None) is None):
                return fn(context, *args, **kwargs)
            if latest is None or not latest.matches(context):
                latest = PreparedOwner(context)
                counts['owner_scopes'] += 1
            token = active.set(latest)
            try:
                return fn(context, *args, **kwargs)
            finally:
                active.reset(token)
        return call

    def memoized(fn, attribute, label):
        @wraps(fn)
        def call(key):
            owner = owned()
            if owner is None:
                return fn(key)
            table = getattr(owner, attribute)
            if key not in table:
                counts[label + '_miss'] += 1
                table[key] = fn(key)
            else:
                counts[label + '_hit'] += 1
            return table[key]
        return call

    def lowerers(fn):
        @wraps(fn)
        def call():
            owner = owned()
            if owner is None:
                return fn()
            if owner.lowerers is None:
                counts['lowerers_miss'] += 1
                owner.lowerers = fn()
            else:
                counts['lowerers_hit'] += 1
            return owner.lowerers
        return call

    def source_registry(fn):
        @wraps(fn)
        def call():
            owner = owned()
            if owner is None:
                return fn()
            if owner.canonical_registry is None:
                counts['source_registry_miss'] += 1
                fresh = fn()
                # Only reuse the actual context's registry if the complete
                # registered adapter set (including callables) matches.
                if fresh._by_generator == owner.source_registry._by_generator:
                    counts['source_registry_owner_reuse'] += 1
                    owner.canonical_registry = owner.source_registry
                else:
                    counts['source_registry_owner_mismatch'] += 1
                    owner.canonical_registry = fresh
            else:
                counts['source_registry_hit'] += 1
            return owner.canonical_registry
        return call

    targets = {
        id(registry.default_registry): memoized(registry.default_registry, 'registries', 'operator_registry'),
        id(registry._implementation_digest): memoized(registry._implementation_digest, 'implementation_digest', 'operator_digest'),
        id(school.live_source_registry): source_registry(school.live_source_registry),
        id(task_goal_registry.live_task_goal_lowerers): lowerers(task_goal_registry.live_task_goal_lowerers),
    }
    modules = [m for m in tuple(sys.modules.values())
               if m is not None and getattr(m, '__name__', '').startswith('bilqis_mlx.')]
    scope_names = ('_learning_first_task_goals', 'factory_evaluation_instruments',
                   'factory_evaluation_case_from_source')
    for module in modules:
        for name in scope_names:
            fn = vars(module).get(name)
            if callable(fn) and id(fn) not in targets:
                targets[id(fn)] = around(fn)
    for module in modules:
        for name, value in tuple(vars(module).items()):
            if id(value) in targets:
                setattr(module, name, targets[id(value)])
    return counts
