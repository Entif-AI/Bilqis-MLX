# A05.1 causal streaming partial-frame compiler | implementation receipt

- Issue: #408; parent A05 #357; Lane A
- Branch: `codex/bamf02-a-semantics`
- Consumed unified trunk:
  `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
  (verified ancestor, no no-op merge)
- Consumed A03.3 #404, A04.3 #407, A13.3 #432
  source/codec/context contracts. Independent leaf
  EGM PASS is recorded in A03/A04/A13 `egm.md`.
- Implementation head: pending immutable commit/push
- Independent A05.1 EGM: **PENDING**

## Owned behavior

`bilqis_mlx/semantics/frame_compiler.py` adds
`compile_prefix(ast, visible_end, release, compiler_config)
-> CompiledFrameBatch` and
`reconstruct(compiled) -> VisibleAST`.
Input `StreamingAST` consists of source-adapter
visible atoms with immutable positions and already
source-bound A03 `FrameTree` records. A05.1 does not
invent source atoms, change a released schema, or
consume evaluator gold.

Before a frame is complete, the output contains only
the raw source atoms visible at the requested prefix.
No packed frame, frame handle, hidden member or future
sidecar is emitted. The closing boundary is the latest
of the A03 frame causal end, A13 envelope causal end
and every constituent's source-visible prefix.
Only then does the compiler re-run A13
`project_context` against the exact prefix, pack the
frame using A04 `pack_frame`, and append a closure
reference at that closing source position.

No earlier position is rewritten. Independent roots
use canonical source order; nested children close
before parents. Reconstruct validates A04 sidecars,
preserves atomic and extended frames, and rebuilds
the visible frame forest. A source frame may remain
incomplete indefinitely, including an atom-only
stream with no approved complete frame.

The content-addressed `CompiledFrameBatch.cache_key`
depends only on the requested source ID, semantic
release, visible prefix, frozen schema map, approved
*visible* context digest and emitted positions.
Future source atoms, future frame content, gold labels
and later requests do not enter the key. A changed
future member cannot affect the earlier prefix;
when a delayed constituent finally becomes visible,
its closure is appended at that later position,
never inserted into a consumed cache prefix.

## Schema versions

- `bilqis.streaming-source-ast/v1`
- `bilqis.streaming-source-atom/v1`
- `bilqis.frame-compiler-config/v1`
- `bilqis.compiled-prefix-position/v1`
- `bilqis.compiled-frame-batch/v1`
- `bilqis.visible-source-ast/v1`
- Consumed `bilqis.semantic-frame-instance/v2`,
  `bilqis.packed-frame/v1`,
  `bilqis.context-approved-projection/v1`

## Focused executable evidence

Owner `test_frame_compiler.py`: **11 passed, 0 failed,
0 skipped**. Four-member literal frame prefixes
0..8 show no early frame handles; the final frame
uses the actual compact 13-bit codec. Future-token
and future-member changes preserve earlier compiled
objects and cache keys. Nested child/parent/atomic
closures round-trip, including delayed member closure,
reordered source roots and source rows of unequal
lengths. Revoked A13 frame grants fail closed before
packing. Network access is trapped.

Adjacent A03/A04/A13 suites plus A05.1:
**63 passed, 0 failed, 1 optional skip**.

**Staged status:** `COMPILER_PREFIX_PASS;
NEURAL_F05_PENDING_B11`. This is not a neural-logit
equivalence claim. A05.2/A05.3 and A05 parent
integration remain open. No optimizer/student state,
source-rights promotion, live training, unified merge
or main merge occurred.
