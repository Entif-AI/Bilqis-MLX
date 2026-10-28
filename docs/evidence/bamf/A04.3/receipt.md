# A04.3 ordered frame constituent and codec-sidecar evidence

Issue: #407
Lane: `codex/bamf02-a-semantics`
Consumed unified: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed A04.2 candidate: `9b9a2886d2c24452a7c7f813dd84b4a11f2c31de`
Review disposition: `EGM_PENDING`

## Exact sidecar contract

`FrameSidecar` is a frozen, versioned record bound to the selected compact,
extended or atomic codec, semantic release, content-addressed schema map,
canonical frame payload SHA-256, and original occurrence/content identities.
For typed frames it also preserves the full schema ID/revision/SHA,
AST construct, order mode and scope. Source-instance identity, structural
path, source span, parent occurrence and causal-prefix end are separate
fields, not reconstructed from a compressed semantic index.

The ordered `ConstituentMetadata` sequence retains every role ID and
occurrence index, binding state, semantic ID, semantic release, ABI index,
type IDs, exact source reference and child occurrence/content/type metadata.
Its explicit order index preserves original constituent order, including
distinct roles with the same type. A present ABI index zero remains
`(0,)` with VALUE state; UNKNOWN has an empty index tuple and a distinct
state. Extended and atomic frames retain their canonical original payload
instead of inventing compact members.

`PackedFrame.projection_sha256` binds codec disposition and sidecar
identity. It is a derived representation digest, not a new semantic ID.
Two source occurrences with identical role content retain the same
`FrameInstance.content_digest` but distinct occurrence IDs and projection
digests. The semantic release, ABI index and content identity remain
separate from this derived projection.

On unpack, the codec validates the canonical schema, schema-map identity,
compact/extended slot agreement, payload schema ID/revision, all concept
semantic releases and the complete expected sidecar. A payload and sidecar
jointly substituted to name a foreign frame cannot be returned merely
because the compact indices happen to match.

## Executed behavior and boundaries

Focused `scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_codec.py`:
14 passed, 0 failed, 0 skipped.

The tests assert literal compact words, zero-versus-presence, ordered
role metadata and source references, same-content/different-occurrence
identity, partial UNKNOWN state, extended/atomic exact reconstruction,
and the upper uint32 boundary. A coordinated foreign-schema/foreign-release
payload substitution was observed accepting invalid input before the
explicit binding repair; it now raises the registered codec error.

The combined actual-source adapter and codec tests passed 25/25 with no
skips. `git diff --check` passed. This work touches only semantic
frame representation and evidence. It does not authorize source promotion,
neural admission, optimizer updates, live training or a merge.

The previous independent A04.2 review is preserved as an open finding
until a fresh immutable-head EGM reviewer confirms the repair. No
independent sign-off is claimed here.

## 2026-10-28 schema-contract review repair

The codec now checks the released frame schema's role ordering,
cardinality, occurrence sequence and allowed types on both pack
and unpack. A valid sidecar cannot make an invalid frame eligible
for EXTENDED representation. The focused codec suite passes
17/17 after the repair. Independent review of the new immutable
head returned **EGM PASS at `9e3ec5b`**, with zero remaining
Blockers/Majors. The reviewer inspected source/tests only; 17/17
is prime executed evidence. No parent or integration gate is closed.
