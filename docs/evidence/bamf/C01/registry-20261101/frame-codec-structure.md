# C01 frame-codec structural interruption — 1 November 2026

Work Stack `59d77f15-1d25-4af5-9527-de2939b126de`, task
`struct-frame-codec`, is the last of five encountered structural repairs. Original
interface-receipt work remains preserved until this interruption is verified.

The original 984-line codec is a 91-line public facade. Its 13-file private package
separates wire primitives, schema tags, compact words, sidecar records, packed
records, classification, sidecar construction, atomic payloads, packing, validation,
unpacking and readout. Largest source owner: 160 lines. The original 670-line
companion becomes an absolute fixture compatibility facade; 14 mirrored test-package
files remain below 240 lines, with largest 144. Neither directory reaches 18 files.

All 32 original production class/function ASTs and all constant expressions remain
identical. The public/private exports, canonical class/enum/function identities,
runtime annotations, error fields, bit layout, canonical bytes, source/schema
checks and active/held readout gates are preserved. The owner graph is acyclic.
There is no copied issuer, token, registry or new source-admission authority.

Sixteen original test methods, setup, four fixtures and all comments retain their
original ASTs. The 86-line readout witness becomes two focused scenarios: successful
compact/extended lookup and inactive/held rejection. Original statements/assertions
remain in order; only schema/map setup repeats. Four new witnesses check canonical
UTF8/newline bytes, typed sidecar rejection, all 11 codec class/enum pickle identities
and the schema-map factory return annotation. The codec selection now has 22 cases.

Verification:

- Original baseline: 17/17; new characterization cases: 4/4.
- Record extraction and full procedure extraction: 21/21 at each checkpoint.
- Mirrored test move/readout split: 22/22.
- Combined source selection: 164/164, zero failures/skips, with both real Atlas
  artifact and canonical corpus fixtures. All four legacy fixture-file targets load.
- Staged size/hygiene: PASS across 29 Python files, zero findings/new debt.
  Architecture, governance, documentation, error-control and diff checks pass.
- Fresh independent readiness and implementation reviews report zero Blockers,
  Majors or Nits. Reviewers compared ASTs, constants, assertions, comments, metadata,
  annotation dependencies, owner graph and limits; they did not execute tests.
- Exact-candidate native proof and isolated installed-wheel proof remain required
  before the interruption's complete scoped verification is recorded.

Portable reproduction adds `bilqis_mlx/semantics/tests/frame_codec` and its legacy
fixture-file target to the frame-schema evidence's 142-case command. Supply the
same two real asset variables. Compact literal words, little-endian bytes, decimal
JSON, slot-zero presence, uint32 boundaries, authoritative role validation, typed
fallbacks, exact reconstruction and rejection of altered source/schema sidecars
must retain their existing results.

The installed-wheel selection must load only installed `bilqis_mlx` modules from a
fresh target under Python isolated mode and `/tmp` cwd. Its expected 93 cases exclude
70 repository BAMF script tests and one vendor-only source fixture. Those exclusions
do not replace the full 164-case source proof. Unexpected skips or module origins
outside the installed target fail the probe.

Consumes reviewed unified/Lane C `bd62f3cb`. No threshold/baseline, learner, AdamW,
training, graph or source-admission change, and no self-merge. Full #347 remains
open with eight holds and no executable order.

Exact source commit `4ab0752d` passed all six native M3 caller cases without skips
in a detached checkout under the sovereign MLX test lease. Cumulative structure
and hygiene checks pass across 112 Python files, with zero findings/new debt.
The isolated installed wheel passed 93/93 with both real fixtures, no skips and
verified installed module origins. The [later installed-wheel recipe](installed-wheel-probe.md)
records the subsequent 116-case selection, wheel identities and repository-only
exclusions; it does not supply the historical 93-case wheel hash or selector.

All five mandatory structural predicates are now locally satisfied. Completing
this Work Stack interruption permits the original interface-receipt work to resume;
it does not establish full C01 acceptance or permission to self-merge.

## Current-unified reconciliation — 2 November 2026

The resumed candidate consumes reviewed unified
`67c964a1` through Lane C `46bfa98d`. Unified has independently accepted
`frame_codec_parts`, its 56-line public facade and codec-neutral source-type
authority checks. Keep those owners and remove this branch's superseded
`_frame_codec` extraction. All 32 top-level class/function ASTs and named constant
expressions agree except the accepted `role_index` type-authority guards; those
guards remain intact.

Retain both test sets. The older focused readout tests now use the accepted
authoritative-concept fixture for active/inactive readout; held-semantic rejection
and every original assertion remain. The first combined run reports 183 passes,
one fixture-expectation failure and two errors among 186 cases. One fixture error
and the expectation failure are the missing authoritative concepts. The other
error is the public schema-map annotation NameError tracked by #731. No production
validation or source authority is weakened. The historical 164/93/6 receipts above
remain tied to their original heads until current candidate verification completes.
