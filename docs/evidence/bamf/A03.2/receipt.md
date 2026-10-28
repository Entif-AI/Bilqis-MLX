# A03.2 validated frame bindings and atomic fallback evidence

Issue: #403
Lane: `codex/bamf02-a-semantics`
Consumed unified head: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed A03.1 head: `adc85149686b09ccc552276d5ded7e083c7d6a99`
Review disposition: `EGM_PENDING`

## Implemented contract

`RoleOccurrence` now carries a declared `BindingState`: `VALUE`,
`NONE`, `UNKNOWN`, or `ALTERNATIVES`. NONE and UNKNOWN are explicit
records, never missing dictionary keys or fabricated semantic rows. Unresolved
alternatives retain the exact candidate `ConceptRef` values.

`validate_frame_bindings` and `bind_frame_instance` enforce the released
`RoleSpec` cardinalities, contiguous occurrence indices, allowed concept
types, frozen Atlas semantic release and ABI index, declared frame scope, and
source-visible causal prefix. Bindings are ordered by released schema-role order
and then occurrence index.

The cumulative A03.3 review repair additionally closes the incoming type and
serialization boundaries. For a source-qualified Atlas concept, caller-supplied
`ConceptRef.type_ids` must equal the canonical types in the frozen Atlas
concept record; a forged type is rejected even when the role explicitly allows
that forged type. Formal-domain refs are constructed by the released source
adapter from the existing source semantic-graph/native-operation signature
rather than a second type registry.

`FrameInstance` now verifies its occurrence ID from source-instance identity
plus structural path, verifies its content digest from schema identity plus
bindings, and requires `causal_prefix_end >= source_span.end` in the frozen
record constructor itself. These checks therefore apply equally to normal
binding and canonical deserialization.

`bind_ast_frames` accepts the native AST/source node plus the frozen Atlas.
When an approved frame schema is supplied it validates and emits a
`FrameInstance`. When no approved schema exists it emits an `AtomicFrame`
that preserves canonical source data, source span, occurrence identity,
structural path and causal prefix without inventing semantic meaning.

## Parent acceptance witnesses

- Singular role duplication fails with `FRAME_ROLE_CARDINALITY_INVALID`.
- An explicitly plural role accepts occurrence 0 and occurrence 1 distinctly.
- NONE, UNKNOWN and ALTERNATIVES survive canonical frame-instance roundtrip.
- Role type mismatch, declared-scope mismatch and future causal-prefix use fail
  closed.
- A valid canonical semantic ID/index with a caller-forged, role-allowed type is
  rejected by Atlas concept type authority.
- Serialized occurrence-ID, content-digest and causal-prefix tampering is
  rejected before the frame can be returned.
- A `ConceptRef` from a foreign semantic release fails before any neural use.
- Nested negation/scope preserves the child occurrence and child content digest;
  the child is not flattened into the parent.
- An unapproved AST construct takes the atomic fallback and returns the exact
  original source object through the immutable sidecar.
- A03.1 TRANSFER role-swap, same-type-role and occurrence/content identity
  witnesses remain green.

## Verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_schema.py` after
the cumulative boundary repair: 12 passed and 1 external real-Atlas witness
skipped in ordinary mode. With the pinned real canonical Atlas bundle enabled:
13 passed, 0 failed, 0 skipped. The real witness uses an actual source-qualified
canonical Atlas concept for the forged-type regression. The cumulative package
also proves that a native `Apply` with the right symbol/signature but a changed
semantic contract SHA cannot satisfy a released frame schema.

`frame_schema.py` is 662 lines and all functions remain below the 300-line
hard function limit. `scripts/check_module_size.py` reports no A01/A03
regression; its nonzero repository result is the three inherited shared-runtime
size findings outside this lane.

`scripts/error_control_plane.py --check` reports no frame/Atlas debt; its
nonzero repository result is limited to the inherited shared
scheduler/plasticity/runtime findings.

`git diff --check`: passed. No trainer/model/optimizer write path is imported
or executed, and the implementation has no grade-specific runtime branch.
