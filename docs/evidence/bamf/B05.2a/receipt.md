# BAMF-0.2 B05.2a / issue #863 proof receipt

Status: turned-in proof; independent EGM and hosted PR checks passed on the
semantic/test proof head. Human merge remains external authority.

## Authority and baseline

- GitHub issue: #863, `BAMF-0.2 B05.2a | Execute B01 adapters after source-backed group selection`.
- Parent: #450 / B05.2. This receipt does not close or broaden the parent.
- Reviewed unified consumed before issue-owned work:
  `08654dd2efd199cda03527bc456c3631f3cc0dbb`.
- Working branch: `codex/863-b05-2a-source-adapters-20261110`.
- No neural optimizer run, source grant, parameter ledger, accepted-generation mutation,
  teacher mutation, or self-merge is authorized or performed here.

## Implementation finding

Current reviewed unified already contains the source-owner implementation required by
this decomposed leaf: the B11 source producer applies the existing B01 rank-eight
adapter immediately after each B05 selection at boundaries one and two, and
`finalize_source_backbone_hidden` applies the third adapter to the final boundary
without executing a fourth backbone group. Receipt replay re-derives the same
adapter inputs from the producer-owned complete B01 parameter tree.

The missing acceptance surface was a source-backed observable-behavior witness.
`test_backbone_source_adapters.py` supplies that witness without adding production
authority or a duplicate implementation.

## Direct proof

Using the existing reproduced A01 Atlas bundle whose content identity is
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`:

- nonzero adapter A/B weights change the selected boundary state and the exact
  adapted digest becomes the real group-two and group-three input;
- boundary three returns the manually reconstructed adapted tensor while the
  producer remains at exactly three executed groups and four source receipts
  (`h0`, `g1`, `g2`, `g3`);
- gradients through the real final output are finite and nonzero for A and B in
  all three adapters;
- zero-initialized B preserves the pre-adapter selected input exactly;
- stale/cross-boundary depth substitution and foreign parameter-tree substitution
  fail closed without executing another group.

The expected adapter result in the test is independently reconstructed with the
literal RMSNorm -> A -> SiLU -> B / rank equation rather than by calling
`adapter_forward` to manufacture its own oracle.

## Verification

Focused new witness:

```text
4 passed, 0 failed, 0 skipped
```

Affected source-owner ring:

```text
21 passed, 0 failed, 2 skipped
```

The two explicit skips are retained-motif/B08-B13 fixture obligations outside this
leaf's authority. The issue's pinned A01 source-adapter witness executed with zero
skips.

Repository guards:

```text
PASS: 43/43 exact checked-in issue mirrors equal workstack SHA-256 receipts
PASS: 43/43 issue API, implementation and acceptance fields match workstack
BAMF_FLOW_CONTROL_OK
```

## Independent EGM and hosted turn-in

Fresh independent Goldfish EGM reviewed exact semantic/test proof head
`269f4d04051493f5e68ce7d6164aacc7bdb0390c` against reviewed unified
`08654dd2efd199cda03527bc456c3631f3cc0dbb` and returned:

```text
PASS
Blocker 0 / Major 0 / Nit 0
```

The reviewer independently inspected the live #863 acceptance, source producer,
finalizer, replay, depth selection, adapter ownership, and retained B08/B13 path.
It also reproduced the pinned-A01 source-adapter witness at 4/4 PASS with zero
skips and the lower-level adapter suite at 6/6 PASS.

Draft PR #981 hosted checks on the proof head:

```text
semantic-abi-integrity PASS
portable-core          PASS
portable               PASS
```

The subsequent turn-in commit is documentation/flow-control bookkeeping only and
does not change production or test semantics. Merge remains human-only, issue #863
remains open until merged readback, and parent #450 remains open regardless of this
child's merge.
