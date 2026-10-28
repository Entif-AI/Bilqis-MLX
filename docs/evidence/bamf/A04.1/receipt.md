# A04.1 exact compact-frame v1 codec evidence

Issue: #405
Lane: `codex/bamf02-a-semantics`
Consumed unified head: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed A03 candidate: `8b31bc049a2cd4c365a0e96093e4230fbe32bd0c`
Consumed A03 operator-control repair:
`b378255cc16c22cf4e5d14071f6789672a1607c3`
Review disposition: `EGM_PENDING`

## Exact compact layout

`bilqis_mlx/semantics/frame_codec.py` implements the prescribed compact
`bamf.frame-u64/v1` word using integer shifts and masks only:

- slots 0 through 3 each occupy 13 bits, covering bits 0 through 51;
- bits 52 through 55 are the complete presence mask `0b1111`;
- bits 56 through 59 are the release-local schema tag;
- bits 60 through 63 carry codec version 1.

`pack4` accepts exactly four integer indices in `[0, 8191]` and a schema
tag in `[0, 15]`. It always records complete presence. `unpack4` rejects a
wrong version, incomplete/illegal presence, an unknown release-local schema tag,
or a non-u64 input before returning a `SlotTuple`.

Literal vectors:

- `pack4((0, 1, 8190, 8191), 3)` =
  `1441151880624349184` = `0x13fffffff8002000`;
- four zero indices with schema tag 0 =
  `1220475499017404416` = `0x10f0000000000000`;
- four max indices with schema tag 15 =
  `2305843009213693951` = `0x1fffffffffffffff`.

Zero is an ordinary present ABI index: the presence nibble is independent of the
slot value.

## Release-local schema tags

`SchemaTagMap` binds one exact semantic-release SHA to a deterministic set of
`SchemaTagEntry` records. Each entry carries tag, full schema ID/revision and
SHA-256 of the canonical `FrameSchema` bytes. The map's own digest is over its
canonical typed contents, so changing release or full schema changes the map
identity. Schema order at construction does not change the resulting tags or map
digest.

A map can contain at most 16 compact schemas. This leaf rejects a 17th compact
tag rather than truncating it; A04.2 owns the typed extended fallback for that
condition.

## Wire form

`serialize_u64` writes exactly eight little-endian bytes and returns the
explicit codec identifier plus a decimal-string representation safe for JSON.
For the mixed literal vector above, the exact byte sequence is
`002000f8ffffff13`. `deserialize_u64` reconstructs the same integer and the
typed byte record rejects a decimal string that disagrees with its bytes.

## Verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_codec.py`:
6 passed, 0 failed, 0 skipped.

The cumulative frame-schema package remains 12 passed with one external
real-Atlas witness skipped in ordinary mode, and the real registered
source-frame adapters remain 7/7 passed.

`scripts/error_control_plane.py --check` reports no Atlas/frame/codec debt.
Its repository-wide nonzero result consists only of the nine inherited
scheduler/plasticity/runtime findings already owned outside Lane A.

`scripts/check_module_size.py` reports no new A01/A03/A04 hard-limit debt.
The repository-wide nonzero result remains the three inherited shared-runtime
size regressions. `frame_codec.py` is 245 lines and all codec functions are
below the 300-line function limit.

`git diff --check`: passed. The compact codec contains no neural/model,
optimizer, trainer, or grade-specific runtime path. It encodes identity indices
only; source-admission/readout eligibility remains a later shared-accessor
boundary owned by A04.2.
