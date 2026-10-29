# A05.2 source-position maps and isolated batch receipts

- Issue: #409; parent A05 #357; Lane A
- Consumed unified:
  `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
  (verified ancestor, no no-op merge)
- Direct predecessor A05.1 #408 implementation:
  `84bba19cd00206f6d3fa55f76c23866f584315c8`
  with receipt `e4317684e8589324ad2ceb0011eca1d50f0180c5`
- Pushed implementation head:
  `8065c52ee2c4cd4436fa92a3d0ddf7f5599036c7`
- PR #546 native Development closing reference #409
  verified by GitHub GraphQL readback
- Independent A05.2 EGM: **PENDING**

## Source and boundary maps

The A05.1 `CompiledFrameBatch` now exposes immutable
`maps: PrefixMaps` derived entirely from source-visible
positions and A04 packed sidecars:

- `position_to_source` retains the source span,
  source reference and ATOM/CLOSURE distinction for
  each compiled position.
- `source_to_positions` maps each visible source atom
  to its raw position and every covering frame closure,
  including a delayed closing boundary.
- `prefix_ends` gives the cumulative compiled-position
  end for every source prefix, without rewriting
  previously emitted positions.
- `scope_boundaries` preserves the task-row scope and
  exact frame scope ranges through the closing position.
- `padding_mask` distinguishes real positions from
  non-source batch padding.
- `role_access` preserves ordered role ID,
  occurrence index, VALUE/NONE/UNKNOWN state,
  semantic IDs, ABI indices (including zero), and
  source references from the A04 sidecar.
- `expansion_handles` binds the approved frame handle,
  occurrence/content identities, source span, compiled
  position and projection digest.

The `CompiledFrameBatch` schema advances from the
A05.1 original `bilqis.compiled-frame-batch/v1` to
`bilqis.compiled-frame-batch/v2`. Its cache digest
now includes task scope and the explicit policy
version tuple `(policy_id, policy_epoch, rights_epoch,
correction_generation)`, in addition to the existing
release, schema map, visible context and positions.
This is a deliberate same-branch interface migration,
not an alternate source-of-truth schema.

`compile_prefix_rows` returns a frozen
`CompiledFrameRows` object. Each row is compiled
independently, then padded with `None` positions
and `False` mask entries to the maximum row width.
Padding never enters a row's source maps, role access,
prefix ends or cache identity.

## Schema versions

- `bilqis.compiled-frame-batch/v2`
- `bilqis.compiled-prefix-maps/v1`
- `bilqis.compiled-frame-rows/v1`
- Other A05.1 input and position schema versions
  remain unchanged.

## Executed evidence

Owner `test_frame_compiler.py`: **14 passed,
0 failed, 0 skipped**. The four-member frame
produces literal prefix ends `(0,1,2,3,4,5,6,7,9)`,
role IDs `slot0..slot3`, ABI indices `0..3`,
and exact source-reference maps. Changing the policy
epoch changes the compiler cache key without changing
source positions. Two unequal source rows produce
independent compiled rows, distinct keys and a
`(True,True,True,False,...)` padding mask on the
shorter row. Changing only the other row does not
change its positions, maps or cache key.

Adjacent A03/A04/A13 plus A05 tests:
**66 passed, 0 failed, 1 optional skip**.

**Staged status:** `COMPILER_PREFIX_PASS;
NEURAL_F05_PENDING_B11`. A05.3 and A05 parent
integration remain open. This does not authorize
student/optimizer training, source promotion or
merging the draft Lane A PR.
