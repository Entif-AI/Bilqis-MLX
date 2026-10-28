# A04.2 typed extended fallback and shared readout evidence

Issue: #406
Lane: `codex/bamf02-a-semantics`
Consumed unified head: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed A04.1 head: `91d62a563cee69145c26911868c0d7da9f096f92`
Intervening A03 numeric-contract repair:
`0a7f8e6b54b91caa03fda7365cc1676312a1bf86`
Review disposition: `EGM_PENDING`

## Typed representation selection

`classify_frame` returns a `PackDecision` with explicit
`PackDisposition` and `FallbackReason`; fallback never depends on catching
an arbitrary encoder exception.

Compact v1 is selected only when:

- the exact full `FrameSchema` has a release-local compact tag;
- the schema is exactly four singular roles;
- the frame contains exactly four distinct role occurrences;
- all four bindings are VALUE concept refs with no child frame;
- every ABI index fits the 13-bit compact range.

All other valid frames select a typed extended or atomic representation.
`FallbackReason` distinguishes unavailable schema tag, non-four/singular
schema, slot count, repeated role occurrence, non-VALUE binding, child frame,
13-bit index overflow, and atomic source frame.

## Canonical extended representation

`ExtendedSlot` preserves exact role ID, occurrence index, binding state,
uint32 ABI indices, semantic IDs, and typed child occurrence/content references.
It accepts indices through the uint32 extended domain while compact remains
strictly 13-bit.

`PackedFrame` binds every representation to:

- semantic release;
- content-addressed schema-map digest;
- full schema ID/revision/SHA and canonical schema bytes when a schema exists;
- canonical frame payload;
- compact word or canonical extended slot array;
- explicit codec ID and typed fallback reason.

`unpack_frame` verifies the release and schema-map identity, canonical schema
payload/digest, compact tag-to-full-schema identity, and compact/extended slot
agreement with the canonical frame sidecar before returning the exact original
`FrameInstance` or `AtomicFrame`.

Literal fallback witnesses prove exact reconstruction for:

- a 17th full schema outside the 16 compact tags;
- ABI index 8192;
- a five-slot frame;
- a nested child frame;
- a partial frame with an UNKNOWN role;
- an atomic unknown-source frame.

## One readout boundary for both codecs

`role_index(packed, role_id, occurrence_index, schema_map=..., snapshot=...)`
is the single semantic-index accessor for compact and extended storage.
It reconstructs/verifies the packed frame first, then checks:

- exact semantic release;
- held-source identity;
- semantic ID membership in the frozen ABI;
- sidecar ABI index equality;
- active-set state.

Storage and neural readout are therefore separate phases. A source-qualified
inactive ABI row can be represented and persisted, including in compact v1 when
its index is below 8192, but `role_index` rejects it with
`FRAME_READOUT_INDEX_INACTIVE`. A forged held semantic ID that borrows an
active in-range index is rejected with `FRAME_READOUT_SEMANTIC_HELD`.

The same accessor returns the expected index from both a compact four-slot frame
and an extended five-slot frame.

## Sidecar reinterpretation resistance

Decoding with a schema map from the wrong semantic release fails explicitly.
Using a same-release map whose full schema differs also fails via the
content-addressed map identity. A compact tag is therefore never sufficient
authority to reinterpret a frame under another release or full schema.

## Verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_codec.py`:
11 passed, 0 failed, 0 skipped.

The cumulative frame-schema package remains 12 passed with one external
real-Atlas witness skipped in ordinary mode; the actual registered source-frame
adapter package is 8/8 passed.

`scripts/error_control_plane.py --check` reports no Atlas/frame/codec debt.
The repository-wide nonzero result contains only the nine inherited
scheduler/plasticity/runtime findings.

`scripts/check_module_size.py` reports no new A01/A03/A04 hard-limit debt.
The repository-wide nonzero result remains the three inherited shared-runtime
regressions. `frame_codec.py` is 696 lines and no codec function exceeds the
300-line hard limit.

`git diff --check`: passed. No neural state, model parameters, optimizer state,
or grade-specific runtime path is read or written by the codec.

## 2026-10-28 codec review repair

The earlier independent A04.2 review identified a schema-identity hole:
the canonical payload could carry a different frame schema with identical
ABI indices while the packed schema sidecar was valid in isolation. The
codec now binds the decoded `FrameInstance` schema ID/revision and every
concept's semantic release to the validated packed schema and release
before returning the frame or allowing `role_index` readout. The mandatory
typed `FrameSidecar` also binds the full constituent metadata and exact
payload hash, with comparison against the decoded payload.

The new regression first failed with a coordinated frame-payload and
sidecar substitution, then passed after the explicit schema/release checks.
It rejects a foreign schema with identical indices and a foreign semantic
release even when the attacker recomputes the visible sidecar fields.
The upper uint32 boundary is now directly witnessed: index
`4294967295` round-trips through extended encoding; index `4294967296`
rejects with `FRAME_EXTENDED_SLOT_INVALID`.

Focused `test_frame_codec.py`: 14 passed, 0 failed, 0 skipped.
Combined adapter/codec suite: 25 passed, 0 failed, 0 skipped.
The previous independent review findings are repaired and tested locally;
fresh immutable-head EGM remains `EGM_PENDING` rather than claimed.
No neural state or source admission was changed.
