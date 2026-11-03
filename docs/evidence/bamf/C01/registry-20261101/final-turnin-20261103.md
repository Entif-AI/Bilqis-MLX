# C01 final turn-in proof and scope map — 3 November 2026

This receipt binds the C01 structural integration candidate to the exact PR #803
turn-in after its final current-unified merge. It supersedes older aggregate
counts and lineage statements only for final merge-readiness; historical receipts
remain evidence for the source commits they name.

## Exact integration identity

- PR #803 candidate before this documentation-only closeout:
  `f13abd7c8afee13a5fdcaae86b43e1efae0dd724`.
- Its parents are C01 candidate
  `961390b4313cf210703d1fe7575f55dcaa03fb12` and reviewed unified
  `05e31a576e3432e4238c9b4477a70d70ec4fc487`.
- The final merge-forward added the reviewed-unified B13.4 schema witness and
  reconciled Lane B/Lane C flow-control records. The diff from `961390b4` to
  `f13abd7c` changes no C01 production semantic implementation path.
- Semantic ABI hosted verification passed on `f13abd7c`. Hosted portable-core
  stops at the live open-PR DRAIN gate; that administrative inventory failure is
  distinct from C01 semantic verification.

## Exact-head deterministic proof

Both previously verified source fixtures were supplied read-only by their
content-addressed identities: A01 artifact
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
and conformance corpus
`f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`.
No machine-local fixture path is part of this receipt.

The complete final C01 source selection adds the six mandatory
`semantics/_public_identity/tests` cases and the three recursive
`test_public_facade_dependencies` census cases to the historical owner selection.
On the exact `f13abd7c` checkout and independently from a fresh Git archive of
that same commit:

- source selection: **209/209**, zero failures/errors/skips;
- fresh wheel/isolated installed target: **132/132**, zero
  failures/errors/skips, with every loaded `bilqis_mlx` file and namespace
  resolving under the installed target;
- one repository-only released-schema IO fixture remains the explicit installed
  exclusion and is covered by the source selection;
- wheel SHA-256:
  `e9f201d9277270b4ae98610fbfa2a8c7651aac22fed5bf1e60b83f7bca397508`;
- disposable native MLX frame callers: **6/6 on CPU**, zero
  failures/errors/skips, with CPU still selected after the run.

These 209/132 totals replace the stale 200/126 aggregate numbers for final
turn-in. The earlier counts remain valid only for the historical source snapshots
that recorded them.

## Aggregate scope and ownership map

The 126-file aggregate is a parent integration of already governed C01 structural
and remediation work. It does not assign new semantic behavior ownership to Lane C.

| Changed family | Authority / owner | Consumed repair | Acceptance evidence |
| --- | --- | --- | --- |
| Causal compiler facade/private owners and mirrored tests | C01 #347 mandatory development interruption, Work Stack task `struct-frame-compiler`; semantic behavior remains with the existing semantics owner | Original C01 structural lineage | `compiler-structure.md`, final 209/132/6 aggregate |
| Partial-visible-forest facade/private owners and mirrored tests | C01 #347 mandatory development interruption, task `struct-partial-forest`; existing semantics authority preserved | Original C01 structural lineage | `partial-forest-structure.md`, final aggregate |
| Released-frame-schema facade/private owners and tests | C01 #347 mandatory development interruption, task `struct-released-schemas`; existing A01/A03 source authority preserved | Structural lineage plus #786 public-hook repair | `released-schemas-structure.md`, `round3-repairs-20261103.md`, final aggregate |
| Frame-schema facade/private owners and mirrored tests | C01 #347 mandatory development interruption, task `struct-frame-schema`; existing semantics/source authority preserved | Original C01 structural lineage | `frame-schema-structure.md`, final aggregate |
| Frame-codec facade/private owners and mirrored tests | C01 #347 mandatory development interruption, task `struct-frame-codec`; codec semantics remain unchanged | Original C01 structural lineage | `frame-codec-structure.md`, final aggregate |
| Public callable/module identity restoration | #771 | `3174c368` lineage consumed by C01 | `public-callable-identity-771.md`; mandatory six cases included in 209/132 |
| Contract/registry verifier reconciliation | #770 | consumed at `47188f53` | `integrated-20261103.md` and verifier/registry receipts |
| Released-schema public verification fault seams | #786 | `6f0dd50d` | `round3-repairs-20261103.md`; final source selection |
| Current proof-total validation | #787 | `d2d2a0bf` | `round3-repairs-20261103.md`; final 209/132 predicates |
| Late-bound public-facade dependency repair and recursive census | #800 | semantic repair `d2d88078` consumed by parent | `late-bound-facade-20261103.md`; three census cases included in 209/132 |
| Native CPU reproduction contract | #801 | `bd376f28`, consumed through parent merge `1205b990` | `native-cpu-recipe-801.md`; final exact-head 6/6 CPU replay |
| B13.4 schema witness and live flow-control records arriving in the final merge-forward | reviewed unified `05e31a57`, not new C01 semantic ownership | final merge `f13abd7c` | final-merge diff plus hosted Semantic ABI PASS |

The C01 parent remains an integration/ownership parent. The five large semantics
files were changed because the repository's mandatory development interruption
was triggered while C01 was executing; their structural extraction preserves the
existing semantic owners and public interfaces. Remediation issues record the
specific defects found during review and were consumed into this parent rather
than creating replacement semantic authority.

## Remaining parent scope

This turn-in proves the scoped C01 structural merge candidate. It does not close
full #347, does not clear its eight normalization holds or create an executable
order, and does not claim source admission, retained learning, student/AdamW,
teacher, graph, or human-run mutation.

The candidate's EGM episode remains `C01-STRUCTURE-20261103`. Any EGM finding
about stale counts, exact-head lineage, reproduction parameterization or scope
mapping is mechanically decidable from this receipt and the cited deterministic
proof; no behavior-changing repair is represented here.
