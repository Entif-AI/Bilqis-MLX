# C05 evaluation source-custody checkpoint — 2026-11-07

## Scope

This checkpoint closes one integration defect in the open C05 owner surface: the
Factory evaluation compiler already received the canonical source AST from the
source owner, but discarded that AST before constructing the B11
`CompiledEncoderInput`. Training already preserved the same source material.

This is not C05 parent completion, B06 composition, or a new source authority.
Completed child #501 remains closed.

## Exact identity

- reviewed unified base: `bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`
- branch: `codex/378-c05-eval-ast-20261107`
- semantic head: `7db57cdca52457403fd26a936f09b6944ce53ccc`

## Change

`compile_factory_evaluation_batch(...)` now validates the compiled visible
prefix against the exact source AST with the existing A05
`validate_partial_visible_forest(...)` owner and carries both the AST and its
receipt into `CompiledEncoderInput`.

No B06 policy, caller credential, consumer-local grant, source record, learner,
optimizer, retention rule, or publication authority changes.

## Proof

Exact-head `m3-ultra` witness, pinned to `7db57cdc...` and the accepted A01
artifact:

- focused C05 evaluation custody: 1/1 PASS in 7.441s
- focused custody + cheap B13.2 continuation helper ring: 4/4 PASS in 10.117s
- foreign source-instance substitution rejects under the existing partial-forest
  validator

Repository checks on the same branch:

- `python3 -B scripts/check_bamf_flow_control.py`: PASS
- `python3 -B scripts/check_module_size.py ...`: 0 violations
- `python3 -B scripts/verify_bamf_0_2_contracts.py`: PASS, 43/43 mirrors and
  214 owner/child identities/fingerprints
- `BILQIS_QUALITY_BASE_REF=origin/codex/bamf-unified-base-20261028 npm run quality:changed`:
  PASS; 0 changed-file smell findings; legacy trainer 6/6; flow-control 15/15
- `git diff --check`: clean

A first attempted command referenced the nonexistent historical helper
`scripts/check_bamf_contracts.py`; no product code ran under that command. The
current verifier is `scripts/verify_bamf_0_2_contracts.py`, which passed.

## Remaining authority boundary

This scoped branch is not a merge-ready C05 parent candidate and does not spend a
fresh EGM. Final C05 integration/acceptance still belongs to #378 and its current
direct dependency/owner graph. The B06/#471 chain still requires three other
upstream authorities before B11 may compose B06.2 into B06.3:

1. source-owner issuance of the complete compiled-prefix inventory grant,
2. persisted operator `run_seed` plus true visit identity,
3. authoritative request disposition for explicit-member, unresolved-nested and
   ordinary requests.

The C05 evaluation AST/partial-forest custody gap is no longer one of those
missing implementation seams on this branch, but downstream work must consume it
through reviewed integration rather than a sibling merge.
