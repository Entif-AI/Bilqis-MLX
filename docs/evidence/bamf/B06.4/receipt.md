# B06.4 | Refinement tensor registry reconciliation

## Authority and scope

Issue #455 owns the final B06 refinement tensor and initializer reconciliation. The accepted B06 parent amendment on #365 keeps B01 as the sole tensor/initializer authority, B06.1 as the private numerical owner, and B11 as the production composition owner. B06.3/#454 is closed and its PR #942 is merged.

This candidate consumes reviewed unified `036e0aa3c2bec184481a4f009d8c31e16b9495f5`. Its final semantic/test proof head is `f8f61dc1674269c323ddd55258df88069033fce6`.

Historical PRs #686 and #725 remain closed provenance. Their accepted repair semantics were remapped onto the current `bilqis_mlx/runtime/_depth/atlas_refinement.py` owner. The retired `refine_selected(...)` facade was not restored.

The stale `refine_selected(...)` wording in the original live #455 body and its checked-in source mirror is preserved as historical task provenance. The accepted #365 B06 authority amendment supersedes that physical/API wording and governs this implementation.

## Implemented contract

`refinement_parameter_view(...)` validates the complete B01 parameter tree before projecting any refinement tensors. It derives its ordered declarations from B01 `expected_bamf_shapes(...)` and returns exact aliases to the existing `refine.*` arrays.

The projection is a tuple-backed MLX parameter pytree with a named lookup surface. It is immutable and carries no self-attested topology, extents, declaration, or ownership authority. B01 provenance is re-derived against the complete validated parameter tree, topology, and generation extents at the verification boundary. MLX autodiff reconstructions therefore cannot self-ratify as B01 authority. Numerical validation reads tuple leaves directly, so replacing the named accessor cannot substitute tensors.

B01 remains the only initializer owner. The proof compares each projected tensor with `initialize_bamf_parameter(...)` and the B01 manifest fields for shape, initializer, optimizer group, and decay.

The current B11 production path is unchanged. It obtains this view from the accepted full parameter tree and passes it into the existing private B06 recurrence.

## Verification

Focused current-head proof:

- B06.4 registry: 12/12 PASS, zero skips or errors.
- Existing B06.1 numerical refinement: 7/7 PASS, zero skips or errors.
- Whole refinement owner family: 22/22 PASS, zero skips or errors.
- Real-A01 B11 production refinement: 9/9 PASS, zero skips or errors.
- B01 topology/ledger/initializer/lifecycle: 21/23 PASS, with two declared optional witness skips and no failures or errors.

The real-A01 witness used the pinned artifact at:
`/Users/emilie/Code/371-c02-complete-20261106/.local/c02-a01-rebuild/5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`.

Repository gates:

- BAMF contracts: 43/43 exact mirrors and 43/43 API/implementation/acceptance fields.
- Governance integrity: 0 violations.
- Factory architecture: PASS.
- Semantic boundaries: PASS.
- BAMF flow control: PASS.
- Docs: PASS.
- Changed-file code-smell audit: 0 findings.
- Error-control plane: new debt 0.
- Current changed-scope structure/governance: 0 violations.
- Diff check: clean.

Final differential leaf selection on the repaired semantic head:

- exact base: `036e0aa3c2bec184481a4f009d8c31e16b9495f5`;
- selected changed/dependent suites: refinement registry, existing refinement numerics, and grouped runtime identity;
- result: **24 tests PASS + 80 subtests PASS**, zero failures or errors.

The repository-wide premerge test sweep also ran on this branch and reached
`3,941 total / 3,528 passed / 236 skipped / 13 failures / 164 errors`.
That aggregate is **not recorded as a passing qualification**. It is dominated
by repository/environment failures outside the #455 change surface, including
many `DISK_BUDGET_EXHAUSTED` custody/publication paths and unrelated semantic
and integration failures. No aggregate failure identity is in the B06.4
registry/refinement owner or the exercised B11 production refinement ring.
The changed-scope differential gate above is green.

The full `npm run verify:premerge` quality phase also stops earlier on three
legacy-trainer authority violations in unchanged evidence files. The identical
legacy-trainer failure reproduces on pristine reviewed unified
`036e0aa3c2bec184481a4f009d8c31e16b9495f5`, so it is base-owned debt rather
than a #455 regression.

The two topology skips are owner-declared capability gates: `BILQIS_BAMF_FULL_WITNESS` and `BILQIS_V1_BUNDLE_WITNESS`. This leaf does not convert absent optional witnesses into passes.

## Historical failure closure

The historical pinned EGM review of the old #455 candidate found two Majors: the registry projection was not directly differentiable as an MLX parameter tree, and a dict-shaped view could be mutated through the base dict API. This candidate carries the #715 repair into the current production owner.

Fresh review of the first current-unified repair then found a third candidate-owned Major: the view's dynamically generated class stored its provenance predicate in mutable class state, which `type.__setattr__` could replace. The repaired design removes self-attested authority from the differentiable view entirely. Regression proof now establishes direct `mx.grad(...)` traversal, blocks base-container substitution, re-derives B01 provenance from the complete authoritative tree, survives the class-monkeypatch exploit, and prevents accessor replacement from changing numerical consumption.

## Final independent review

Two fresh exact-SHA Goldfish reviews were rebound after the provenance repair
to semantic/test head `f8f61dc1674269c323ddd55258df88069033fce6`.

- Codebase/authority review: **0 Blockers / 0 Majors / 0 Nits**, `TURN_IN YES`,
  `NO_DRIFT`.
- Structural/ownership review: **0 Blockers / 0 Majors / 0 Nits**,
  `TURN_IN YES`.

Both independently confirmed B01 sole registry/initializer ownership, B06.1
private numerical ownership, B11 production composition ownership, complete
tree validation before projection, exact aliasing, absence of self-attested
mutable provenance, and no executable restoration of `refine_selected(...)`.

## Lifecycle

The old #455 flow-control resume condition is satisfied: #454 is accepted and merged, and the #715 repair semantics are consumed here. The issue remains open until fresh post-implementation review, hosted PR checks, human merge, and merged-head readback complete its lifecycle.

No live student, AdamW state, teacher state, accepted checkpoint lineage, or human-run training was mutated.
