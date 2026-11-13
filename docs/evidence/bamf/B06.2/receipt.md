# B06.2 prediction-local refinement selection: scoped candidate

Issue: [#453](https://github.com/Entif-AI/Bilqis-MLX/issues/453)
Lane: B, isolated single-writer candidate `codex/bamf02-b06-policy-20261029`
Consumed Lane B: `7b70b0d4f70c2df7d79ddd69db91a2eaf1da78ae`
Consumed reviewed unified: `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`
Direct prerequisite: B06.1/#452 provisional numerical kernel `8162096`

## Owned software

`runtime/refinement_policy.py` implements a pure prediction-local selector
over the actual A05 compiled source AST and A13 context eligibility.
It replays `compile_prefix` at p against the source-owned AST/config,
requires exact agreement with every compiled closure and the approved
context digest, **and requires an independent source-frontier grant for
the complete compiled p-local cache identity**. An omitted AST frame
changes the inventory digest and cannot be silently reauthorized by
ordinary atom/frame grants. The source owner, not this selector, must
issue that inventory grant. The selector refuses omitted visible frames
before computing Fp.
It filters future frames before source-policy projection and computes the exact
`min(32, ceil(Fp/8))` quota. Requested-role matches rank first, followed by
source-visible salience and stable source span/occurrence order. Salience is
optional, defaults to a neutral tie, and requires an exact source-frontier
grant binding the approved frame envelope, value and visibility. It cannot
authorize a frame, member or learning target.

Each selected record carries the exact
`(input-generation, prediction-boundary, query-ID, frame-occurrence)`
cache identity. Inference uses zero passes ordinarily, one for explicit
member questions and up to two for unresolved nested frames. Training
samples 0/1/2 deterministically from the complete SHA256 of the run seed,
visit ID, p, query ID and occurrence, independent of batch length.
Unselected eligible frames remain recorded as baseline/remaining needs.
No shared backbone state is mutated.

`runtime/atlas_refinement.py` adds a masked auxiliary route loss:
missing labels contribute exactly zero route gradient, while the
separate answer loss still backpropagates through the selected one-
or two-pass numerical kernel. A separate pre-refinement route readout
trains class0 even when the zero-pass numerical kernel returns the
original hidden object and no logits. No teacher target enters selection.

## Verification

Focused affected source and real MLX tests, run with the Mac Studio
Python 3.14 MLX interpreter and the existing pure-Python RDF dependency
path:

```
PYTHONPATH=/Users/emilie/Code/bamf-planning-20261027/.venv/lib/python3.13/site-packages \
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/test_refinement_policy.py \
  bilqis_mlx/runtime/tests/test_atlas_refinement.py \
  bilqis_mlx/runtime/tests/test_block_attnres.py \
  bilqis_mlx/semantics/tests/test_context_eligibility.py \
  bilqis_mlx/semantics/tests/test_frame_compiler.py
```

Result after independent-review repair: **66 passed, 0 failed, 0 skipped**. These include the
8-to-9 quota boundary, future-frame and future-salience isolation,
missing-eligible-frame and truncated-AST adversaries, revoked prefix
inventory grant, source revocation and forged-salience
rejection, all three seeded training pass counts, nested two-pass policy,
measured class0 routing gradients, masked route gradients and retained
answer gradients. `git diff --check` passed. The
error-control-plane checker reported no new findings in either changed
runtime module; unrelated inherited findings remain.

## Boundaries and disposition

**SCOPED_EGM_PASS_INTEGRATION_PENDING.**
Independent EGM at `f612721` found two Majors: a caller could omit an
otherwise eligible frame and shrink Fp, and class0 had no trainable
routing-head path. Both are repaired in the current candidate:
A05 prefix recompilation plus a separately source-granted compiled
inventory digest now bind the complete closure inventory;
`routing_logits_from_state` trains the three-class head without
altering B06.1's exact zero-pass identity. Both repairs were
subsequently independently read back as described below.
An intermediate review at `40c6b16` correctly showed that recompiling
an ungranted caller-truncated AST was insufficient. The additional
prefix-inventory source grant is the follow-up repair.

Independent Goldfish readback at immutable pushed
`9609256fe536d4f512f5a700a63212489d260ea1` returned
**EGM PASS, zero remaining Blockers/Majors**. The reviewer executed
the truncated-AST and source-grant adversaries, including revoked,
forged-digest, stale-epoch, future-observed and future-effective
grants, and confirmed that 66/66 affected tests pass. It performed
no edits. The source owner must still issue the actual prefix
inventory grant in production; this PASS does not admit a live
source, a retained neural generation or the B06 parent.
This is not the public `refine_selected` source/backbone assembly.
B03.3/#444 still awaits A05 child-prefix revalidation and B02
child-binding source factors; B05/B11 must qualify real hidden-state
and summary origin. Source-frontier issuance, query-ID provenance,
source salience issuance and trusted seed/visit identity remain
upstream-owner obligations. The selection record is a replayable
proposal, never a transferable source or neural authority.

No accepted generation, AdamW, live training, source promotion, issue
closure, Lane B shared-branch write or unified merge is claimed.
