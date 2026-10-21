# Issue349 progress review — 2026-10-21

This branch integrates executable factory v2, a typed source frontier, autonomous
teaching/evidence recovery and the first qualified Ithkuil formal realization.
It is ready for progress review, with the limits below. The north-star project
remains incomplete.

Authority: https://github.com/socr8s/private-ip/issues/349 (#349 OPEN) and
https://github.com/socr8s/private-ip/issues/336 (#336 OPEN, IPR-0220).
#335/#339/#340/#343/#344/#345/#348 remain incorporated; #346 is excluded.
Worktree: `/Users/emilie/Code/.worktrees/Bilqis-MLX/349-autonomous-jit-ithkuil-20261020`.
Branch: `codex/349-autonomous-jit-ithkuil-20261020`.

## Continued execution after the review checkpoint

The user asked to continue on this branch. The five legacy A/B system failures
were migrated to the normal executable-release owners. They now exercise actual
toy training, whole-school replay, atomic recovery and preserved historical
student/own-AdamW custody. Championship assertions follow current SPEC-0002
revision 9/10: title jurisdiction is separate from training provenance, and a
qualified challenger takes a defended title on a battery tie. Production
championship policy was not changed.

The fixture migration exposed a real v1-to-v2 resume defect: the old live-rubric
hash remained active after v2 adoption. Migration now binds the current v2 grade
rubric and preserves historical exams and the input receipt. Diagnostics and
fragile replay also treated the v2 envelope schema as the rubric. A shared
`stored_rubric_version` decoder preserves legacy identities and reads v2 rubric
identity separately. Diagnostic v2 readback checks source/release/scope metadata;
routine exam observations receive the actual pointer metadata. The test runner
now prioritizes the repository root for file and dotted targets, avoiding
`scripts/tests` shadowing shared test fixtures. Red regressions captured the
migration, import and diagnostic failures. PM-2026-10-20-003 / RC-116 was enriched
and verified by native ledger readback.

Isolated combined proof: **508 passed, 3 skipped, 0 failed (511 total)** across
factory/runtime, diagnostics, replay, fixed-frontier integration and A/B/Z system
checks, with full B enabled. The final file/dotted runner regression also passes
all 6 checks. The previous hardcoded live-provider release fingerprint in the
opt-in B test was replaced by sealed-manifest roundtrip/preservation checks;
source course identity and transition order remain checked. No ABI validator,
expected ABI fingerprint or audit baseline was changed. 53 inherited hygiene
findings remain; this continuation adds none.

A read-only fresh-seed transfer probe is now reproducible with
`scripts/issue349_transfer_probe.py`. It scores three seeded draws, deduplicates
source identities, records the majority baseline and predictions, verifies native
checkpoint/AdamW and hashes protected files before/after. It writes no admission
evidence. Historical training-exposure overlap remains NOT_MEASURED; these are
fresh-seeded observations, not a guarantee of wholly unseen semantic worlds.

| Current saved run | A.IDENTITY | A.MAPS |
| --- | --- | --- |
| Protected primary, step 116816 | 58/113 | 70/139 |
| Independent control, step 117648 | 73/113 | 88/139 |
| Gold majority baseline | 70/113 | 70/139 |

Both runs stayed byte-identical through these probes. The control's earlier 888
updates produced useful but limited transfer on this sample; the two lineages
are not a matched causal experiment. Neither prerequisite is mastered. D remains
unadopted and untaught. Tracked receipts:
`20261021-issue349-transfer-primary.json` and
`20261021-issue349-transfer-control-before.json`. A subsequent bounded control
visit and paired probe, if performed, must preserve these pre-visit receipts.

## Publication and ownership

The configured origin is `https://github.com/Entif-AI/Bilqis-MLX.git`.
GitHub's repository API returned `private=false`, `visibility=public` on
2026-10-21. The user then confirmed: “It's public now. You can push.” That direct
publication authorization resolves the earlier hold and supersedes the older
private-implementation posture for this branch. Public PR prose screens private
authority links. No visibility change, history rewrite, main merge or issue
closure is required. Source wave `8c0de35a03d2ad8f2b089a35d60e2e99b0b38714` is
followed by this documentation correction. The final execution checkpoint and
remote readback bind the publication head.

The latest source commit must be read with `git rev-parse HEAD`; the private issue
checkpoint binds its exact SHA. A prepared PR body and publication receipt are in
ignored `.local/issue349-source-wave/`. Do not publish that body unscreened to a
public repository. Incident PM-2026-10-21-001 / RC-053 / PAT-039 was filed and
verified by native ledger readback. Earlier visibility history and publication
authority were not established by this preflight.

A separate writer's 36 staged paths implement typed errors/control-plane work.
They are excluded from the source commit. Preserve those files and their index
entries, including their shared `trainer.py` changes. Do not blanket-stage, reset,
stash or claim that the mixed worktree is the isolated review tree. Original index
and patch recovery material is in `.local/issue349-source-wave/`.

## What the branch implements

- Factory v2 owns canonical curriculum definitions, executable profiles, source
  and answer bindings, exact assessment scope and release transitions. The two
  original implementation histories are retained in the amalgamated branch.
- Typed candidate/frontier records and JIT proposals bind source provenance,
  release identity and current checkpoint/native optimizer step. Research
  hypotheses cannot admit themselves or reuse historical mastery as current proof.
- Actual delivered teaching receipts and rejected-attempt receipts distinguish
  retained optimizer progress from unsuccessful trials. Bounded remediation
  defers exhausted obligations and selects other legal work. Source preparation
  continues when learner work is exhausted.
- Tracked later chapters can be extracted in bounded source-only work. Every
  snapshot records missing-sense/provenance debt; source expansion cannot silently
  become semantic admission. Exactly two registered experimental runs share a
  measured 100,000,000,000-byte allocation cap.
- This wave realizes -Č-, Stem1/BSC, sense `LEXSENSE-5286ade9db42c7`, as identity
  across references in a total finite map. A typed AST, strict codec, independently
  interpreted oracle, exhaustive finite-world agreement and balanced seeded
  counterfactual specimens support the package. Other uses of “be” are unsupported.
  Natural Ithkuil morphology remains NOT_REALIZED.
- Token Atlas index 227 was appended with native readback, preserving all prior
  rows. Immutable birth receipts remain distinct from current provider hashes.
  Repeated vocabulary growth preserves earlier allocation provenance.
- `D.COPULAR_IDENTITY` compiles through the ordinary factory into a thin A+D
  profile. It requires A.IDENTITY and A.MAPS. Live staging and proposal revalidation
  reuse existing profile/catalog admission transactions. Automatic new-grade
  uptake requires the normal complete perfect prefix; no debt bypass was added.
- Ordinary teaching, probes, rehearsal, fragile preservation, optional enrichment
  and host preparation consume the admitted v2 release. Source workers receive no
  student, optimizer, teacher/scheduler state or writable learner paths. Neural
  work and persistence remain serialized.

Review source ownership in this order: `source_adapters/copular.py` and
`copular_curriculum.py`; `semantics/copular.py` and `verification/copular.py`;
`factory/candidate_realizations.py`; `runtime/jit_adoption.py`, `autonomy_live.py`
and `candidate_staging.py`; then the release-driven teaching consumers and
`trainer.py`. The detailed source witnesses and prior live failures are preserved
in `ISSUE349_SOURCE_STAGING_HANDOFF_20261020.md` and ADR-075.

## Verification and its limits

Tests ran against an archive of the exact isolated source tree, excluding the
separately staged migration. Ignored historical checkpoint and teacher fixtures
were copied independently and verified; no canonical/historical run was written.

| Proof | Result |
| --- | --- |
| Factory and runtime suites, importable module names | 434 total: 431 passed, 3 skipped, 0 failed |
| Source/oracle, vocabulary and prefetch/typed-answer slice | 33 passed, 0 skipped |
| Grade A/B and generic Grade Z system slice, B opt-in enabled | 29 total: 24 passed, 5 errors |
| Same system slice on pre-wave HEAD `5ea41b9` | The same 5 errors; 24 passed |
| Factory architecture, closure, semantic boundaries and docs |Passed |
| Historical ABI guard |Passed in advisory mode; external expected digest absent |
| Release metadata |0.2.0 passes; no release/tag created |

Hosted semantic-ABI verification passed at the first publication head. Portable
CI stopped at the hygiene gate:53 baseline-relative findings reproduce on the
pre-wave source. The source wave initially added two findings; a red/green
immutability regression and shared profile-validation helper remove those two.
No baseline was regenerated or exemption added. The remaining53 are inherited
branch review debt, so hosted portable verification remains unqualified.

The five baseline system errors are unmigrated fixtures: two calls omit the
required `grade_a_course`/`source_root` resume keywords; three legacy fixtures lack
an admitted executable v2 release. They reproduce before this wave. Grade Z passes
through the generic control plane. This is not a green whole-repository claim.
The older mixed-worktree `DRIFTED` versus typed-error assertion remains separate
migration debt; it was not altered to inflate the source result.

Reproduce focused proof with `PYTHONPATH=.:tests` and
`node /Users/emilie/.codex/hooks/validation-output-runner.mjs -- python3 -B scripts/run_tests.py ...`.
Use importable dotted module names for runtime prefetch tests because spawned
workers cannot import the repository runner's generated hashed-file module name.
Discover the factory/runtime `test_*.py` files, replace `/` with `.`, strip `.py`,
and pass those names to the runner. The system command uses
`BILQIS_FULL_GRADE_B_TESTS=1` and the three files
`tests/system/test_{grade_a_trainer,grade_b_trainer,factory_grade_z}.py`.
Retained failure logs and the isolated tree/index identity are under the local
review directory and `/Users/emilie/.codex/validation-logs/`.

## Empirical evidence and custody

Both trainers are stopped. No optimizer work was launched during review
preparation. Readback on 2026-10-21 confirms:

| Issue-owned run | Generation | Native AdamW step | Checkpoint SHA |
| --- | ---: | ---: | --- |
| `primary` | 356 | 116816 |`260b56c5e194d7b204beceec716cfcbe0d80c52225006fbb1ee0041ccf7d3d1f` |
| `plasticity-control` | 23 | 117648 |`73c432433b7716e04fee9cf63f82683945708c967d85243f179bb06c3a89ba02` |

The protected primary's fresh A.IDENTITY and A.MAPS probes are both 6/12. Source
uptake/staging succeeded without altering its student, own AdamW, state or events.
D remains unadopted and untaught. The student still has 222 vocabulary rows.

The independent unprotected control started at native step 116760 through the
verified historical loader. Three bounded six-visit sweeps at 4, 16, 128 steps per
visit produced fixed-seed probe results 5/12→6/12→6/12→7/12 for A.IDENTITY and
6/12→6/12→5/12→7/12 for A.MAPS, after 0, 24, 120, 888 updates. This is modest movement
on one source probe. It establishes neither prerequisite mastery, fresh
generalization, retention safety nor a matched causal comparison with primary.
No AdamW states were merged and no lineage was synthesized.

Latest measured allocation is **1,441,005,568 bytes** across exactly two runs,
below 100,000,000,000 bytes. This is a new filesystem allocation observation;
older receipt sizes remain historical snapshots. Recompute with
`ExperimentRunBudget(Path('runs/issue-349-experiments')).assert_within_budget()`
before any further run writes. No third experimental directory is authorized.
Tracked receipts are under `docs/evidence/experiments/20261020-issue349-*.json`.

## Next work after progress review

1. Publish under the user's explicit public-repository authorization. Push
   non-force, read back exact remote SHA, append/read back the execution checkpoint,
   open a draft PR with screened references and attach it to the Codex task.
   Do not merge or close the execution issue.
2. Migrate the five legacy system fixtures to admitted v2 release/runtime contracts
   without weakening custody checks. Preserve the independent staged migration.
3. Investigate current prerequisite learnability/transfer in the two existing
   issue-owned runs. Do not turn 7/12 into mastery or bypass full-prefix graduation.
4. Exercise actual student-bound D adoption, teaching, fresh generalization and
   retention/composition only when current evidence justifies admission. Wiring
   tests cannot substitute for that missing empirical result. Legacy unsupported
   D diagnostics remain NOT_MEASURED.
5. Qualify more frontier semantics: 239 of 240 candidates lack a real qualified
   package. Resolve inherited-sense and later canonical-PDF provenance debt before
   promoting those snapshots. Broader composition and communication remain open.

Incidents PM-2026-10-20-001/002/003/004 remain relevant; RC-116 covers the v2
consumer/provenance defects repaired here. Revert source with ordinary commits
while retaining native allocation evidence, experiment bundles, own AdamW and
immutable proposal/evidence history. Never rerun an initializer on an existing run.
