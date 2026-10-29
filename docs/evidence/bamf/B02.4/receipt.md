# B02.4 nested child-frame constituent binding | isolated candidate

Issue: #576 (B02.4). Parent: B02 #347. Dependent B03.3: #444.
Source prerequisite: A05.4 #575, independent EGM pending at this cut.
Lane B base: `ae08c4aa6c9eee86cbc28142de626f382662876d`.
Independent B02.4 EGM: **PENDING**.

## Source and neural contract

`ChildFrameRequest` in `learning/frame_embeddings.py` is a typed
`ChildFrameRef` constituent. It binds the exact A13-approved parent
frame/member handles, source child frame occurrence and content digest,
source-instance identity, parent relation, release and scope. It has no
`ConceptRef`, semantic ID, or ABI index. The A06 factor path uses only
source-declared child type, parent role and parent schema; it never
invents an identity-bank row or graph neighborhood for a child frame.

`CompiledEncoderInput` now accepts a source-owned `StreamingAST`
and exact `PartialVisibleForestReceipt` for each compiled row. The
A05.4 validator rechecks the original source forest and current
A13 grants. A nested row without this source proof rejects, including
the otherwise complete p8 parent tree; the legacy reconstructed
temporary-child-root path is not weakened.

At a child closure the compiled encoder computes its 768-wide seed
from actual source concept members. At a later parent closure, a
typed child constituent reads that **earlier in-row closure output**
and adds source-declared A06 type/role context before the shared
frame encoder. No caller-supplied child vector is accepted. The
public raw `FrameEncoderInput` numerical seam remains concept-only
and rejects `ChildFrameRequest`.

## Executed verification

The new nested test initially failed to import the missing
`ChildFrameRequest` API. With the implementation:

- `test_nested_frame_constituents.py`: **3 passed**, including
  child p4 / parent p8, exact source occurrence and parent reference,
  real MLX parent-to-child member gradient, nonzero child-type factor
  gradient, source-mutation rejection, raw-path child rejection,
  p8-without-A05.4 rejection, and p4 embedding invariance under a
  valid future parent-member change.
- `test_frame_embeddings.py` + `test_frame_encoder.py` + nested:
  **34 passed, 0 failed, 0 skipped** on Apple MLX.
- After provisional A05.4 current-grant repair `8f1b61e`, the combined
  MLX/B02/B03/A05/A13/A04 suite passes **98/98, zero skips**. The
  B02.4 adversary now revokes hidden-parent A13 grants while leaving
  the p4 compiler object unchanged; B03 rejects through the A05.4
  source validator rather than trusting stale approved metadata.
- `git diff --check`: passed.
- Error-control and module-size audits: no new B02.4/B03.3 finding.
  Existing semantic import-boundary findings in A03 remain separate.

## Dependency and integration boundary

The isolated branch temporarily cherry-picks A05.4 implementation
`ad14c7f` as `f1c8b8b` and its live-grant repair `d19ccc7`
as `8f1b61e` solely to compile and verify the dependent
neural path. These are **not** independent B-lane publications of A05
authority. Before merging into Lane B, reconcile the accepted A05.4
source through the reviewed unified integration branch and remove
the provisional duplicate source commit. The B02.4 PR remains draft
until A05.4 independent EGM, cross-lane source integration, and its
own independent EGM PASS. No training, source-rights promotion,
parent closure or lane merge occurred.
