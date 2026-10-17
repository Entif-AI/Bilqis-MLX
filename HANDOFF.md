# Bilqis evergreen factory | untested contracts handoff

**Start here.** The human explicitly requested contracts/scaffolding **without tests**, then transfer to the other machine's fresh quota. Five new Python modules are unfinished and unverified. They were not imported, compiled, tested or executed. They have no live trainer wiring. The receiving agent is authorized to test and analyze them. Do not carry the baseline's green results forward to this WIP.

## Authority and source recovery

- Governing **https://github.com/socr8s/private-ip/issues/336 (#336), OPEN**, parent #335 / IPR-0220; private implementation issue `Entif-AI/bilqis-mlx#1` remains open. Protected source comments `6234271928`, `6233567989` and `6234081376` preserve the generalized ten questions, original mandate/correction and positive-identification clarification. Read them and the latest checkpoint before grade decisions. Keep private links out of public projections.
- Branch **`codex/336-evergreen-factory`**. **Unexecuted source scaffold HEAD: `b88b2fee165b0b76c2fbc74540d7a587cf57da98`**, independently read back from GitHub with matching full tree. This handoff's documentation checkpoint follows that source commit; the latest #336 comment records its exact final SHA. Last tested baseline: **`a28b5f5a5f48ea5068ae0981ffbf4089109174db`**, implementation **`3b3fc257fdccf656ca2bee517c239c3439b1550f`**. Verify current local/GitHub heads before writing.
- Actual M3 feature worktree: **`/Users/emilie/.codex/worktrees/ff64/bilqis-mlx`**. Originally requested `/Users/emilie/Code/bilqis-mlx` stays on `codex/lettergrade-mlx-v1` at `ba97c982ecc399baf76cdf2e3bb95d194045f7a7`; do not repurpose it. Clean feature state and exact baseline were rechecked before WIP. No lease was invented; recheck writers/processes at takeover.
- From MBP: `ssh -T -o Hostname=192.168.0.16 -o HostKeyAlias=192.168.0.92 -o BatchMode=yes m3-ultra`. The IP override uses the previously trusted key. Already on M3, work locally in the feature worktree.
- Correct M3 runtime: **`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`**, 3.14.3 with Torch/MLX. Headless system/Homebrew Python are different environments.

## Read in stages

1. This file, latest #336 checkpoint, root AGENTS/README and append-only ADR; observe the human-student boundary below.
2. [WIP contract guide](docs/architecture/EVERGREEN_CONTRACTS_WIP_20261017.md), then its five modules. The guide contains the full contract rationale, boundaries and focused negative-control matrix. No whole transcript or Registry dump is needed at startup.
3. Inspect existing owners as needed: `curriculum_compiler.py`, `verification/curriculum.py`, `semantics/{core,numeric}.py`, `verification/{cases,laws,review_evidence}.py`, `grade_transition.py`, `vocabulary_growth.py`, `mlx_checkpoint.py`, `next_grade_review.py` and school outboxes. Source/module/ABI contracts `docs/architecture/04`, `05`, `06`, `08`, `09` still govern affected boundaries. The [earlier acceptance report](docs/architecture/EVERGREEN_FACTORY_ACCEPTANCE_20261017.md) describes the verified baseline only.

## Content written, not executed

| File | Draft scope |
| --- | --- |
| `bilqis_mlx/semantics/domains.py` | Source-bound finite domains; literal/decimal-text codecs; binary/finite/native-token answers and declaration hashes |
| `bilqis_mlx/curriculum_contracts.py` | Existing-template leaf/domain bindings, all construction-family dispositions, finite counts and explicit debt |
| `bilqis_mlx/verification/construction_contracts.py` | Catalog-bound final-answer witnesses; pinned finite reconstruction/inverse equivalence receipts through existing proof/law owners |
| `bilqis_mlx/grade_release_plan.py` | Pure disposable cutover intent/observation/actions, parent/staged/committed drift and event-replay obligations; no executor |
| `bilqis_mlx/selection_outcomes.py` | Common-parent/cohort post-replay trials, missing metrics and per-capability Pareto frontier; never selects a grade |

Existing live Python files, source adapters, Registry, model ABI and teacher were not edited. These proposals are unwired and confer no approval. No native Registry or production trust root was fabricated. No test files were written. Commit requests `[skip ci]`; new tests/CI are deliberately deferred. Only source inspection, transport/hash/Git/receipt readback and whitespace checks are permitted in this authoring turn.

## Next executable work on fresh quota

Inspect first; then run import/syntax/serialization checks and write focused tests from the guide's matrix. Fix drafts before integration. Priority:

1. Nested dataclass/mapping hashes; malformed inputs; integer/Boolean distinction; source-complete finite domains; actual native catalog mapping. No core Literal or historical ABI mutation.
2. Input and intermediate domains, canonical roots and prerequisite bindings. The new witness helper checks final output/Catalog binding, not every input/intermediate scope. Do not remove the existing Boolean consumer checks.
3. Source-bound family witnesses/debt discharge. REQUIRED remains debt. Only Apply-to-Apply reconstruction/inverse equivalence is drafted; invalid/negative/contrast and Literal-ending inverses remain unsupported.
4. Independently authenticate executable transformations and bundle readback receipts. Supplied SHA/locator fields are declarations. Extend `verification.review_evidence.VERIFIER_FILES` **when these new helpers become executing consumers**; it currently omits these unwired files. Do not mint approval by hashing one's own proposal.
5. Implement disposable cutover through existing atomic school/outbox/checkpoint owners, not a second journal. Prove every crash/retry window, unchanged own AdamW, append-only catalog, actual 100 GiB reserve and independent complete-bundle readback before operator integration.
6. Independently attest and causally qualify outcomes. Current Pareto comparison covers a common prior assessment substrate, not novel-subject transfer automatically. Preserve negative outcomes and temporary acquisition forgetting; no grade choice or teacher reward.

After focused repairs, run existing review/construction/admission/boundary checks, historical ABI guard and the full M3 suite. These are receiving-agent commands, **not executed in this turn**:

```sh
cd /Users/emilie/.codex/worktrees/ff64/bilqis-mlx
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -B -m unittest \
  tests.test_review_evidence tests.test_next_grade_review \
  tests.test_factory_construction tests.test_curriculum_compiler \
  tests.test_grade_admission tests.test_semantic_module_boundaries -q
# Add and run new focused contract tests, then the full suite at integration.
```

Baseline result only: **440 passed, 2 skipped (442 total)**, hosted CI `39041722509` at `a28b5f5`. The earlier claim of 442 passed plus two skipped was corrected in Git, #336 and the native incident ledger. It is not a result for this new WIP.

## Actual student, remaining gates and incidents

Last verified human run: `/Users/emilie/Code/bilqis-mlx/runs/school-mlx-v1`, generation **6824**, step **204072**, `AWAITING_NEXT_GRADE`; human-operated cumulative A+B **144/144** at one complete student. Recorded full hashes:

- Student **and own native AdamW**: `e65d62174b7c9681991d27e3e2a424358f38dceeb50c90544803bc94d7546585`.
- State/teacher/pointers: `5ec458dfc779629ec4256072be3f29c9d7d225291fd3b2e780510ecd9062a77e`.
- Event ledger: `2812a23caf411c94fd80162721086e1eb817e1e20e59a4a0e1186c54ffa302a2`.

All five recorded file hashes are in `docs/EVERGREEN_SOURCE_ONLY_CUSTODY_20261017.json`. Recheck live bytes at takeover; the human could continue independently. No agent `--human-run`, actual neural update or student/teacher/soup/champion mutation is authorized. Preserve original identities, archives, FP32/own AdamW and **100 GiB reserve**.

**C remains blocked** by `GRADE_C_NATIVE_REGISTRY_ARTIFACT_MISSING` and `GRADE_C_SELECTION_REVIEW_NOT_QUALIFIED`; **D is unselected**. Authentic source/catalog packages, NI grammar/lexicon morphology, generic runtime cutover, wider output qualification and measured recursive learning/health benefit remain unfinished. Historical spreadsheet tranches are provenance, not scheduling authority. No semantic primitives or admitted meanings were added.

Baseline historical replay covers 750 B exams; 39 older records lack modern scope lineage. Three exploratory settings proposed no current quarantine; detection quality/attention/causal benefit remained NOT_MEASURED. Health/retention/reward remain shadow-only. Retain 33 typed-but-not-source-proven cross-world positions, calibrated peer/champion baseline debt and unresolved full-batch champion lesson allocation. Preserve legacy `old`/`preview` separate-question counts and `distill` retention-row KL semantics. No policy remapping or veto of allowed temporary forgetting.

Existing **PM-2026-10-17-003**, RC-095/096/097 and PAT-076, was natively read back including the accounting correction. C-source **PM-2026-10-17-002**, composition **PM-2026-10-16-003**, classroom **PM-2026-10-16-001 through -006** and teacher-boundary **PM-2026-10-14-014** remain applicable. Newly discovered material failures require immediate BIOS failure-intelligence filing/enrichment and native readback; do not duplicate existing incidents or wait until fixes.

## Transport and next checkpoint

Authoring mirror `/tmp/bilqis-evergreen.K2Fw4m` on MBP is not a checkout. The actual feature branch is on M3. Its bare relay `/tmp/bilqis-evergreen.K2Fw4m/relay.git` receives source-only Git bundles and pushes through `gh auth git-credential`; no models are copied. Do not reset the unrelated MBP `/Users/cr8s/Code/bilqis-mlx`. Remote tracking refs may be stale after relay pushes; compare authoritative GitHub branch SHA.

Headless M3 HTTPS Git credentials failed previously. Prefer ordinary non-force pushes if the receiving environment has working credentials. An earlier workflow-scope rejection was resolved by the connected GitHub connector's exact expected-parent non-force ref update; no scope expansion or force push. Use that only if necessary.

Next checkpoint must record exact source/head, observed versus untested work, remaining gates, applicable incidents and human boundary in #336, with remote readback and an updated current handoff. No merge, public projection, issue closure, policy activation, real neural continuation or full-factory completion follows from this WIP.
