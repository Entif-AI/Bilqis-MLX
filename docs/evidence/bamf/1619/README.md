# #1619: Cross-visit and durable cache economics

Disposition: keep existing in-memory reuse. Do not introduce a production
persistent computation cache on this evidence. The two disposable experiments
passed, but neither establishes an end-to-end improvement in useful learning.

## Existing owners

| Artifact | Owner | Reuse boundary |
| --- | --- | --- |
| Accepted hydration and execution bindings | `runtime/_custody/bamf_bundle/accepted_execution_cache.py`, `execution_cache.py` | Same authenticated accepted generation, source registry, topology, extents, and live object identity. A candidate has its own execution binding. |
| Fixed-school parent assessment | `runtime/_capability/factory/_factory_parent_assessment_cache.py` (#1166) | Exact accepted parent, fixed cohort, source, release, evaluation, and policy identities. Challenger evaluation remains fresh. |
| Fixed-school cohort | `runtime/_capability/factory/_factory_fixed_school_trust.py` | Existing immutable C05 receipt and cohort trust. This is not a prediction cache. |
| Derived attention KV | `runtime/_model/cache/`, B14 (#375) | Generation, causal prefix, scope, rights, topology, codec, and quality policy. Reference evaluation stays FP32. |
| Immutable object and file custody | `_data_plane/store.py`, `file_objects.py`, `cache.py` | Content-addressed objects or files, with existing SQLite references and stat-bound file integrity proofs. |
| Frozen advisers | #1609 | The owner controls live adviser inference reuse. Changed school identity or adviser membership requires invalidation. Championship defenses require fresh inference. |
| Training graph | #1615, #1616, #1618, #821 | Reuse must preserve differentiation through the current parameters. Detached results cannot replace a loss-bearing graph. |

The spike uses the existing `DataPlane` object-reference API. It changes no
schema, cache owner, production inference path, or admission policy. Source-only
preparation and registry reuse remain #1617's scope.

## Matched measurements

The detached job passed on 2026-11-24. The base is
`83671fea5420e13499d83c92b31ca96f44b2a4fc`. The exact source snapshot is
`b06b503c8f980fcbc67257cdae9ed6602c0ae3187cf1044b78e48e44525ad487`.
[Raw timings and identity receipts](timing.json) retain individual samples,
the launcher result, and the original witness file digests.
[Confirmation on the final scripts](confirmation.json) records a second passing
run after splitting two long functions. Both the assessment digest and the
restored FP32 output digest matched the detached run exactly.

Each arm uses the same fixture, numerical inputs, and configuration across
eight requests. The table reports local medians from the first run. The microbenchmark does not establish
exclusive accelerator occupancy or predict production wall time.

| Artifact | Recompute | Memory | Durable lookup/restore | Raw payload | Compressed object |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16-case C05 assessment audit record | 103.334 ms | 4.957 ms | 0.214 ms | 26,849 B | 2,921 B |
| Detached FP32 gather, 4,096 rows of width 2 | 0.189 ms | 0.015 ms | 0.347 ms | 32,768 B | 1,475 B |

The C05 fixture recomputed 128 solver contexts. The existing memory cache
used 16 contexts and hit on seven of eight requests. Its eight-request wall
time saved about 877 ms relative to repeated recomputation.

The durable arm retrieves an audit record containing replay records, scores,
and digests. It does not restore a typed, executable Assessment. The measured
0.214 ms is therefore a lower-bound retrieval cost, not an alternative C05
evaluation time. Encoding the audit record alone took 0.115 ms. Publishing
its complete envelope through the data plane took 1.606 ms. Cold-process
lookup took 0.340 ms after a 0.757 ms data-plane open; process startup and
imports increased the full subprocess time to 818 ms. The existing cache
already removes most repeated evaluation within a session. Persistence would
only have incremental value across a session boundary or actual eviction.

The native gather is a lossless FP32 materialized tensor. Its memory cache hit
on all eight requests after population. The durable cache also hit on all
eight, but its lookup and restoration cost exceeded recomputation. Including
one measured recompute as population cost, memory reuse saved about 1.23 ms
over eight requests. Durable reuse cost an extra 2.63 ms, including population,
serialization, and publication. Transfer and encoding took 0.076 ms, and
publication took 0.979 ms. Initial dependency binding took 0.184 ms, comparable
to the gather itself. Do not repeat that binding work on every access.

The confirmation run produced a 0.688 ms median recompute, 0.026 ms memory
lookup, and 0.308 ms durable restore. The recomputation samples varied from
0.208 to 0.869 ms. Including population costs, memory reuse saved 3.46 ms
and durable reuse cost an extra 0.42 ms. The C05 medians stayed near the
first run (102.230, 5.155, and 0.213 ms). Durable lookup latency alone did
not predict net savings. These short trials do not establish a stable
production hit rate or accelerator timing distribution.

The compressed sizes exclude SQLite and archive overhead. In particular,
the gather repeats two fixture rows and compresses unusually well. Real
activation tensors may require substantially more storage and transfer time.
The recorded peak MLX memory in this small fixture was 114,888 bytes.

## Invalidation and custody

The audit witness changes each of the 21 parent binding fields independently
and changes the source revision. Every altered key misses. It also writes an
intact CAS record under the wrong reference and verifies that the embedded
dependency identity rejects it.

The native witness publishes an isolated B13 generation zero with a synthetic
2-by-2 FP32 identity bank and its own AdamW. It performs a real B12 candidate
step and rejects that transaction. The retained object, optimizer digest,
accepted manifest, and cached output remain unchanged. A clean child process
then loads the accepted B13 state and restores the exact FP32 gather.

An accepted disposable update advances generation 0 to 1 and optimizer step
0 to 1. Its dependent parameter and gather output change. The old artifact
misses both in the current process and on cold resume. Independent mutations
of the source, semantic ABI, compiler, manifest, parameter, state revision,
branch, indices, geometry, and scope also miss. These last cases are
dependency-key adversaries, not live semantic admissions. B14's existing
`test_cache_separation.py` covers the production C07 extension and model-swap
invalidation paths.

No artifact becomes retention, championship, source-admission, or optimizer
authority. The witness does not read or modify a real student or its data plane.
It does not authorize cross-generation hits based on allegedly unchanged
parameter regions.

## Decision for #1614

Do not persist inexpensive tensors simply because their dependency keys can
be made stable. A useful candidate must have a measured recomputation cost
greater than its lookup, validation, and restore cost. Publication and storage
cost must also amortize across observed hits.

Use a stable owner-issued identity once per immutable accepted boundary.
B13 already issues accepted execution bindings. This experiment hashes the
small fixture state at its binding boundary; it does not establish production
fine-grained revision authority. Do not replace full-weight rehashing with
another per-hit recursive digest.

Durable assessment evidence is worth further investigation only if a measured
cold-resume or eviction cost justifies a typed, authenticated restore through
C05. Keep fresh championship inference, current-source eligibility, and strict
verification intact. Do not create a second persistence subsystem.

Native attempted steps/minute, completed teacher trials/hour, and fixed
independent competence change/hour are not measured here. The native fixture
uses a synthetic B12 objective, not a teacher visit or curriculum assessment.
Since the spike proposes no production change, it supplies no end-to-end
speedup claim and does not count toward the fivefold program target.

## Reproduce

From the repository root on an MLX-capable host:

```sh
python3.14 -B -m scripts.bamf.profiling.issue1619_cache_economics "$(git rev-parse HEAD)"
```

The witness uses temporary databases, a disposable learner, and subprocesses
for cold reads. Use the repository detached launcher for longer campaigns.
