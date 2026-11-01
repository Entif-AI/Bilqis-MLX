# B14.2 | Quantized norms and small-record FP32 fallback

Issue: #483. Parent cache integration: #375. Authority: IPR-0220.

## Inputs and ownership

Lane B sync `e73e9478e39db51c1349da8b0bbd6ef9209c68d8` consumes reviewed
unified `bb626d75eb0e7d5a8efbb9c0ac10d37cf038e197`.
The branch is `codex/bamf02-b14-2-483-finish-20261101`, with one serialized writer.
B14.1 direction coding is already integrated. This issue recovers the B14.2 record
owner and tests from staged `c43b688565731df416649641838a148d2d8de00e`, without
merging its obsolete predecessor branches or changing accepted B14.1 code.

## Observable contract

`encode_cold_cache(cache, codec_manifest)` consumes finite FP32 two-dimensional
24-channel records. Records under 256 vectors preserve canonical little-endian
FP32 bytes. Larger records pad only the last 32-vector block. Each block stores
one FP32 maximum norm and 32 uint8 relative norms. Directions use the integrated
B14.1 transform/codebook and literal 3-bit packing. Decode inverse-rotates,
renormalizes direction and restores the quantized norm. Original zero vectors
return exact zeros. Canonical zero padding is checked before return.

The new `atlas_cache_records` owner is imported through the public
`atlas_cache_codec` API. Tests mirror the record owner under the current
`runtime/tests/model/attention/cache` directory. No trainer or attention call site uses
these lossy records yet. Cache generation/rights/prefix validation, record header
and effective-bit accounting, attention fidelity policy and FP32 recomputation
belong to #484/#485 and parent #375. Complete B13 generation custody remains open.

## Verification

Baseline integrated direction codec: 11 passed, zero skips.
Red: recovered record tests fail importing the absent record API.
Initial green: direction plus record tests: 19 passed, zero skips.
Boundary probes then exposed FP32 norm overflow/underflow and lossy input conversion.
Incident `PM-2026-11-01-001` was filed and read back before repair. Fresh pinned
EGM independently confirmed these Majors and reported no additional findings.
Red boundary suite: 6 failing cases. Repair requires exact FP32 inputs, accumulates
norms and reconstructs scales in FP64, rejects norms beyond the FP32 storage range,
and permits representable subnormal output rounding. Repaired suite: 22 passed,
zero skips, including large/tiny/subnormal scale and typed rejection witnesses.
Targeted independent re-review: PASS, zero Blockers/Majors/Nits. Reviewer independently ran 22/22 tests with zero skips.

Structure, governance, architecture, changed-path hygiene and documentation checks
pass. Whole-repository error control reports 30 pre-existing findings; clean-base
output is byte-identical (30 diagnostics). No guard or baseline is changed.

Run:

```sh
python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/model/attention/cache/test_atlas_cache_codec.py bilqis_mlx/runtime/tests/model/attention/cache/test_atlas_cache_records.py
```

All vectors are disposable CPU NumPy fixtures. No actual learner, native AdamW,
teacher, checkpoint, source release or human-run was modified. B14.2 completion
is bounded to its three norm/size-policy clauses, not parent cache acceptance.
