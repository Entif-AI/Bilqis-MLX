# B05.3 selector identity and cold-custody proof — 3 November 2026

Issue #451 uses isolated branch
`codex/bamf02-b-451-selector-custody-20261103`, cut from Lane B at consumed reviewed
unified `e9226be2f6a41f47109ca02a1103a363e64909a7`. Lane B already equaled that
unified head, so no no-op merge was manufactured. B05.2's usable numerical and
diagnostic interface is present; accepted PR #802 supplies the B01/B13 schema seam.

The new package-local test joins the existing full B01 native constructor,
B12 optimizer constructor, named selector views and real B13 writer/cold reader.
It changes no runtime behavior or serialized format. This is an **UNBOUND
selector identity/custody witness**, not a source-qualified learner or complete
B05/B08/B11/B13 acceptance.

## Owned proof

- The constructor parameter names equal the full expanded ParameterSpec census;
  constructor manifest cardinality and names agree, and selector metadata matches
  B01 shape, initializer, category and update-group declarations. Decay flags come
  from the same ledger.
- `depth.norm` and the four `depth.query/key/value/output` matrices are singular
  shared tensor identities across all three selector views. Each view's vector
  and bias are the exact `depth.gate.{group}` parameters for that boundary.
- Adding a semantic bank adds only `identity.bank.1`; it does not duplicate shared
  depth paths. Native gate vectors are zero, biases are log(1/9), and effective
  initial gates are 0.01. Alpha is finite and sums to one at each source axis.
- Actual B13 cold load preserves all eleven depth weights, their moments and
  counts by shape, dtype and value. Output, alpha and gate are exactly unchanged
  at all three numerical selector boundaries. Optimizer step remains zero.
- Misowning a shared projection or third boundary gate under `blocks.0` rejects
  through the real B01-validated depth view.

The source-member coordinates are the existing approved synthetic B02 fixture;
source summaries use the explicitly private numerical diagnostic interface. This
proves persistence and identity without borrowing B08 motif or B11 backbone
production authority. No source-held entry is admitted by this proof.

## Validation

With Python 3.14 and the native dependencies recorded in the B08 source-context
receipt, selecting CPU before tests:

```sh
BILQIS_BAMF_FULL_WITNESS=1 python3 -B - <<'PY'
import runpy
import mlx.core as mx
mx.set_default_device(mx.cpu)
main = runpy.run_path('scripts/run_tests.py')['main']
raise SystemExit(main([
    'bilqis_mlx/runtime/tests/depth/test_selector_custody.py',
]))
PY
```

The final full-geometry witness passes **1/1**, zero skips, in 10.232 seconds.
All six pre-existing depth test files pass **18/18**, zero skips. The full witness
uses the real complete constructor, writer and cold reader; no tensor shape,
parameter initializer, reserve or custody predicate is patched. Only its disposable
SQLite data-plane location is selected. The normal 100 GiB reserve remains active.
Default execution without the opt-in variable records an explicit allocation skip.

Ordinary independent GPT-6.1 Terra High review caught a proof gap: distinct gate
objects alone could miss a boundary permutation because initial values match.
The test now asserts each view's exact named vector and bias identity. The same
ordinary reviewer verified the repair with no remaining findings. The 1/1 native
witness was rerun afterward. No artificial production failure or behavior repair
is claimed for this verification-only change.

## Turn-in boundary

No whole-candidate EGM has been requested. Current live Lane B integration PR #809
already owns the lane's integration candidate; PR #808 belongs to Lane C. Final
#451 turn-in must wait for Lane B candidate admission, reconcile the current live
ledger, synchronize once if required, run affected gates and perform pinned
whole-candidate EGM under one persistent review episode. This proof does not
consume a Goldfish round by itself. Do not open another queue-marker PR.

Issue #451 remains open. Full B05.2 source-authorized motif placement and the
assembled parent contracts remain separate. IPR-0220 stays opaque. No actual
student, optimizer update, teacher, checkpoint lineage, source, graph, human-run
or self-merge mutation was performed.

## Continuation — 5 November 2026

ADR-128 supersedes the former one-PR-per-lane admission hold above. #451 was
selected ACTIVE, and this candidate consumed unified
`70a4ef1e883d348920d64083c7546f443a90ef77` in merge
`815e649aa25782ce147dac3a56fd7efe963ae1d8`. The #450 numerical candidate
`cb22592c7bf07494b865152cf7dd3f1255926bb9` is an ancestor; its broader
source-authorized dependencies remain separate. B01 #346 and B04 #350 are closed.

The original exact-head evidence was reviewed against the integration diff. The
runner changed, so the original test receipt was not reused as proof of the current
harness. On CPU with `BILQIS_BAMF_FULL_WITNESS=1`, the complete package-local depth
directory passed **19/19, zero skips**, including the full native cold-custody
witness, at merge `815e649a`. The runner reported `TEST_TOTALS total=19 passed=19
failed=0 skipped=0 errors=0`. The shell wrapper's post-run attempt to assign zsh's
read-only `status` variable failed after the runner had reported success; the full
runner output is retained locally at `/tmp/b451-focused-20261105.log`.

This establishes the same UNBOUND owned selector identity and custody scope. It
does not establish source admission, retained learning, or full B05 assembly.
Independent whole-candidate EGM and human integration remain outstanding.
