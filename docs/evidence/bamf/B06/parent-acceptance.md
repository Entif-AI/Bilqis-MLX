# B06 parent acceptance

Issue: #365

This receipt covers only the original B06 acceptance that remained aggregate at
the parent after B06.1-B06.4 closed. It does not create a new production
refinement interface. The accepted #365 amendment remains controlling:
production composition is B11-owned, B06.1 owns the private recurrent numerical
mechanism, B06.2 owns prediction-local selection, B06.3 owns source/backbone
preservation through B11 composition, and B06.4 owns B01 registry reconciliation.

## Exact integration basis

- reviewed unified consumed: 766ac5f1a94202ce1048bcda0c1a2c5cbefec642
- B06.1 #452: CLOSED / COMPLETED / EGM-Passed
- B06.2 #453: CLOSED / COMPLETED / EGM-Passed
- B06.3 #454: CLOSED / COMPLETED / EGM-Passed
- B06.4 #455: CLOSED / COMPLETED / EGM-Passed
- direct B03 #363: CLOSED / COMPLETED
- direct B05 #355: CLOSED / COMPLETED

## Parent acceptance routing

Existing exact-current witnesses cover:

- zero passes are exact identity;
- one/two passes change only the selected local copy;
- original seed/member recall is reused on pass two;
- gradients reach refinement parameters and source-bound B11 inputs;
- prediction-local quota/ranking/cache identity is independent of future frames,
  future salience, and padding;
- the 8-to-9 boundary preserves the earlier fixed-p selection;
- source-visible frame/member identity is preserved through B11 production
  composition;
- B01 remains the sole tensor/initializer registry owner.

test_parent_acceptance.py adds the aggregate-only witnesses that were not owned
by one child:

1. the exact two-pass hidden result and route logits repeat after serializing and
   cold-loading the complete refine.* parameter set;
2. zero local passes return the baseline hidden object while the prediction-local
   selection retains unselected eligible frames as remaining needs;
3. one finite disposable gradient update on an actual source-owned nested
   child-frame fixture reduces a literal child-role refinement target loss.

The existing Factory training acceptance additionally proves that changing the
training target cannot alter the pre-loss logits, which supplies the preserved
future-teacher-target isolation required by the parent.

All witnesses are disposable. They do not update a live student, native AdamW
state, teacher state, accepted checkpoint lineage, source release, or human-run
training.

## Fresh exact-head verification

On the candidate based directly on reviewed unified
766ac5f1a94202ce1048bcda0c1a2c5cbefec642:

- new aggregate parent acceptance: 3/3 PASS, zero skips or errors;
- combined B06 refinement owner plus real-A01 B11 production ring:
  34/34 PASS, zero skips or errors;
- the isolated Factory target-invariance witness
  test_disposable_gradient_is_finite_and_target_cannot_change_logits:
  1/1 PASS;
- BAMF contract mirrors: 43/43 exact plus 43/43
  API/implementation/acceptance fields;
- governance integrity: 0 violations;
- Factory architecture: PASS;
- semantic boundaries: PASS;
- BAMF flow control: PASS;
- docs: PASS;
- staged changed-file smell audit: 1 Python file scanned, 0 findings;
- error-control plane: new debt 0;
- changed-scope structure/governance: 0 violations;
- staged diff hygiene: clean.

The repository differential test selector also ran directly against the exact
reviewed-unified base and selected only the new parent acceptance owner:
3/3 PASS. The aggregate verify:leaf wrapper stops before test selection at four
source-reference violations reported by check_legacy_trainer_authority.py in
unchanged evidence files. The same four violations reproduce identically on pristine reviewed unified
766ac5f1a94202ce1048bcda0c1a2c5cbefec642, so they are not claimed green and
are not attributed to this parent-acceptance patch.

The broader Factory training execution file was also attempted. It produced
3 passes and 3 errors. All three errors occur before their intended assertions
while their shared fixture tries to publish a successor without the now-required
initial-generation bootstrap, raising
BAMF_INITIAL_GENERATION_BOOTSTRAP_REQUIRED. The parent target-invariance test in
that same file passes when run in isolation. The complete file was then replayed
on pristine reviewed unified 766ac5f1 and reproduced the same 3 passes / 3
errors at the same bootstrap guard. This broader fixture result is not recorded
as a passing qualification and is not used to manufacture B06 evidence.

## Post-implementation drift

Current repository governance separates pre-implementation EGM design review
from engineering verification and post-implementation drift. The accepted #365
authority amendment already received pinned EGM design review. Historical
finished-code Goldfish wording in the original B06 packet predates ADR-137 and
remains provenance rather than a new implementation-review gate.

The complete candidate diff from reviewed unified 766ac5f1 contains only this
acceptance test and this evidence receipt. No production B01, B06, B11, source,
Factory, optimizer, checkpoint, schema, or public API surface changes. The
integrated B06 implementation therefore remains the exact EGM-approved
architecture consumed from reviewed unified.

Drift classification: NO_DRIFT. No design amendment or EGM rerun is required.
