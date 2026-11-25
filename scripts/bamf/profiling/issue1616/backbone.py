"""Issue #1616: opt-in disposable compilation of the existing B11 group graph."""
from collections import OrderedDict
from contextlib import contextmanager
import time
from unittest.mock import patch
import weakref

import mlx.core as mx

from bilqis_mlx.runtime import backbone_group_trace as trace
from bilqis_mlx.runtime.atlas_attention import (
    AttentionCache, AttentionScope, QKVConvolutionCache,
    _attention_parameter_digest, _attention_parameters,
)
from bilqis_mlx.runtime.backbone_group_inputs import validated_group_parameters


STOCK = trace.run_backbone_group_trace
CAPACITY = 12


def _signature(value):
    return tuple(value.shape), str(value.dtype)


def cache_tensors(cache):
    conv = cache.convolution
    return (cache.key, cache.value, conv.query, conv.key, conv.value,
            conv.last_scope, cache.scope_ids, cache.sequence_ids, cache.valid)


def _restore_cache(values, parameters, layer, generation, prefix):
    names = {name: parameters[f"blocks.{layer}.{name}"]
             for name in trace._ATTENTION_PARAMETERS}
    arrays = _attention_parameters(names)
    key, value, q, k, v, last, scopes, sequences, valid = values
    return AttentionCache(
        key, value, QKVConvolutionCache(q, k, v, last),
        scopes, sequences, valid, layer, generation,
        tuple(weakref.ref(item) for item in arrays),
        _attention_parameter_digest(arrays, generation=generation, layer=layer),
        prefix, 0)


class CompiledGroups:
    """One source-release-scoped cache; no persistent or accepted-state authority."""

    def __init__(self, release):
        self.release = release
        self.cache = OrderedDict()
        self.hits = self.misses = self.traces = 0
        self.trace_wall_seconds = self.dispatch_wall_seconds = 0.0

    def _get(self, key, build):
        if key in self.cache:
            self.hits += 1
            self.cache.move_to_end(key)
        else:
            self.misses += 1
            self.cache[key] = build()
            if len(self.cache) > CAPACITY:
                self.cache.popitem(last=False)
        return self.cache[key]

    def _build(self, group, spec, extents, has_starts):
        # Only geometry is closed over. Generation and prefix are rebuilt outside
        # this graph; the stock trace never uses their values in numerical math.
        def numerical(parameters, hidden, scopes, valid, starts):
            started = time.perf_counter()
            self.traces += 1
            result = STOCK(
                hidden, parameters, group_index=group, spec=spec, extents=extents,
                scope_ids=scopes, valid=valid, generation="a" * 64,
                prefix_digest="b" * 64,
                sequence_starts=starts if has_starts else None)
            values = result.hidden, tuple(map(cache_tensors, result.attention_caches))
            self.trace_wall_seconds += time.perf_counter() - started
            return values

        return mx.compile(numerical)

    def __call__(self, hidden, parameters, *, group_index, spec, extents,
                 scope_ids, valid, generation, prefix_digest, sequence_starts=None):
        start, end, required = validated_group_parameters(
            hidden, parameters, group_index, spec, extents, scope_ids, valid,
            sequence_starts)
        # Validate actual caller metadata rather than trusting trace placeholders.
        AttentionScope(scope_ids, start, generation, prefix_digest,
                       sequence_starts=sequence_starts)
        local = {name: parameters[name] for name in sorted(required)}
        starts = (mx.zeros(valid.shape, dtype=mx.bool_)
                  if sequence_starts is None else sequence_starts)
        has_starts = sequence_starts is not None
        key = (
            self.release, spec.digest, extents.digest, group_index, has_starts,
            tuple((name, *_signature(value)) for name, value in local.items()),
            tuple(map(_signature, (hidden, scope_ids, valid, starts))),
        )
        graph = self._get(key, lambda: self._build(
            group_index, spec, extents, has_starts))
        started = time.perf_counter()
        result, caches = graph(local, hidden, scope_ids, valid, starts)
        self.dispatch_wall_seconds += time.perf_counter() - started
        restored = tuple(
            _restore_cache(values, local, layer, generation, prefix_digest)
            for layer, values in zip(range(start, end), caches, strict=True))
        return trace.BackboneGroupTrace(result, group_index, start, end, restored)

    def stats(self):
        return {
            "entries": len(self.cache), "hits": self.hits, "misses": self.misses,
            "python_graph_traces": self.traces,
            "python_trace_wall_seconds": self.trace_wall_seconds,
            "dispatch_wall_seconds": self.dispatch_wall_seconds,
        }

    @contextmanager
    def install(self):
        """Patch only the differentiated session binding for this experiment."""
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )

        def experimental(*args, **kwargs):
            return (STOCK if strict_evidence_enabled() else self)(*args, **kwargs)

        with patch.object(trace, "run_backbone_group_trace", experimental):
            yield
