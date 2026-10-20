# Issue349 autonomous JIT Ithkuil execution | 2026-10-20

Authority: https://github.com/socr8s/private-ip/issues/349 (#349 OPEN); governing https://github.com/socr8s/private-ip/issues/336 (#336 OPEN, IPR-0220). Both remain open. #335/#339/#340/#343/#344/#345/#348 are incorporated authority; #346 remains unrelated/deferred and MUST NOT be absorbed.

Branch `codex/349-autonomous-jit-ithkuil-20261020`, worktree `/Users/emilie/Code/.worktrees/Bilqis-MLX/349-autonomous-jit-ithkuil-20261020`. Base main observed `686438848a4644861febbf11d1b426f770ecb795`. This section describes the post-execution tree before final commit/push; use `git rev-parse HEAD` plus exact `git ls-remote` readback after closeout for the authoritative final SHA.

## Current implemented state

- **Typed non-admitted frontier:** `candidate_frontier.py` verifies the generated source manifest, all source senses/evidence, 144 `CORE_D_O` candidates and 96 reserve candidates. CORE candidates are structurally `PROPOSED_NOT_ADMITTED`; reserve candidates are `CANDIDATE_RESERVE`; both require explicit factory-admission debt. Prerequisite edges remain hypotheses until executable admission.
- **Frontier source closure:** `build_curriculum_frontier.py` now records and validates exact input/output sets, per-file hashes, aggregate digests, builder SHA, exact source/sense inventory, and exact crosswalk root matching. Current regenerated private frontier: 240 candidates, 1,615 senses, 144 core + 96 reserve.
- **Proposal-only JIT path:** `jit_curriculum.py` accepts only exact precompiled successor bindings, verifies source sense/anchor/prerequisites/current-checkpoint mastery, chooses the smallest operation-cost legal slice, and never invokes admission. A candidate cannot smuggle unrelated capability changes: the successor transition must add exactly the selected capability and remove/change none.
- **Current-checkpoint evidence:** the autonomy controller binds every evidence decision to exact checkpoint SHA + optimizer step. No mixed-checkpoint mastery closure. Cross-release evidence carries only when the semantic declaration, source projection, answer-schema projection, coverage projection, and exact obligation remain identical.
- **Truthful teaching receipts:** the trainer receipts only specimens actually emitted by the selected teaching option and actually delivered to the optimizer. Receipt provenance includes option/provider/provider implementation hash/specimen IDs/content digest/variation axes/parent+child checkpoint/AdamW step delta.
- **Crash recovery:** a committed school teaching outbox plus immutable specimen artifact can reconstruct a missing autonomy intervention idempotently after a crash. Cold-start release adoption can reconstruct projection-stable evidence from immutable predecessor factory artifacts.
- **Proactive remediation:** if retention rejects a teaching candidate after the ordinary scheduler has already moved on, autonomy neural-inertly reroutes the failed legal capability back to queue head and emits `SCHOOL_AUTONOMY_TEACHING_REROUTED` before further optimization. It no longer silently trains unrelated work.
- **Issue-owned experiment custody:** `ExperimentRunBudget` enforces issue 349 identity, <=2 direct-child run directories, collective measured allocated bytes <=100,000,000,000, safe pre-write checks, protected checkpoint/state/event/factory/autonomy paths, registry locking, and intermediate-symlink rejection. `--issue-349-experiment-root` wires this owner into the actual trainer; historical/canonical runs remain read-only.

## Verification

After hydrating the repository's intentionally gitignored audited predecessor fixture from the read-only canonical checkout, the combined issue-relevant suite is **404 passed, 3 skipped, 47 subtests passed**. `scripts/check_factory_architecture.py` => `FACTORY_ARCHITECTURE_OK`; `scripts/check_semantic_boundaries.py` => `SEMANTIC_BOUNDARIES_OK`; `git diff --check` passes. The earlier 15 broad-suite errors were all the same missing gitignored historical `.pt` fixture, not code failures; with the exact audited SHA present they disappear.

## Empirical issue-349 run

Exactly one issue-owned run exists: `runs/issue-349-experiments/primary`. Current measured allocation is **519,131,136 bytes** under the 100-GB collective cap; no second run was needed. The read-only audited predecessor source was copied into this worktree's ignored vendor fixture only after SHA verification; no historical/canonical run was mutated.

The first bounded neural attempt exposed two integration bugs rather than being papered over: an executable-v2 school-state decode against the legacy course, then a scheduler/autonomy mismatch after retention rejected A.IDENTITY. Both were repaired and regression-tested.

Empirical causal sequence now demonstrated:

1. fresh exact-checkpoint A.IDENTITY/direct evidence at parent `da50cef3617a4050c06bbd1be3dc2383299046c778774a519ad226fc8890f4a4`, optimizer step 116760, failed;
2. source-grounded teaching option `source.direct/A.IDENTITY` / provider `source.micro.predicates/v1` was delivered with exact specimen receipts;
3. four retained optimizer updates passed the same-grade causal retention screen, producing child `2c5664c13e13718e0a792a5f3d8a806daf2b67640a457e172110310fad653700`, step 116764; local A.IDENTITY +1, same-grade net +1, protected net 0, worst protected loss 0;
4. an exact fresh child-checkpoint EvidenceReceipt was then recorded for A.IDENTITY/direct at step 116764. It still failed the stricter evidence obligation, proving the controller did not confuse a retained local gain with mastery;
5. a subsequent four-step challenger was correctly rejected because its A.IDENTITY +1 was offset by A.MEMBER -1, and the durable student/AdamW remained the retained step-116764 child.

Thus the empirical claim is deliberately narrow: **failure -> reroute -> source-grounded teaching -> causal retention -> truthful intervention receipt -> fresh child-checkpoint remeasurement -> safe rejection/rollback is demonstrated.** Bilqis has not learned all Ithkuil, and this run does not claim Grade-A mastery.

## Remaining work

The source/frontier/JIT machinery is now executable and tested, but automatic frontier expansion is still deliberately separated from admission: there is not yet a trustworthy compiler from a source candidate to a staged executable successor for arbitrary New Ithkuil semantics. When candidate work lacks that exact binding, JIT returns `SOURCE_DEVELOPMENT` instead of inventing semantics or bypassing factory admission. That is the principal remaining north-star gap. Further empirical work should continue in the same issue-owned run unless a materially useful ablation justifies the second authorized directory.

Existing native-ledger incidents still apply: PM-2026-10-20-002 / RC114,RC115 / PAT084; PM-2026-10-20-003 / RC116; PM-2026-10-20-001 / RC113; PM-2026-10-19-004 worktree lifecycle.

No main merge, force push, #349 close, public publication, canonical-run mutation, AdamW merge, or synthesized lineage is authorized or performed.

---

# CURRENT: championship conformance repair queued after durable authority capture (2026-10-19)

**Read this section first. It supersedes conflicting championship instructions below while preserving them as history.**

Current worktree: `/Users/emilie/Code/bilqis-mlx-retention-lab` / `/code/bilqis-mlx-retention-lab`. Branch: `codex/0001-factory-cutover-20261018`. Active human run lineage: `runs/codex-0001-prometheus`. Only the human may start/resume real neural optimizer work. Before any source mutation, re-check for an active human trainer and refuse to hot-edit a running process.

Current governing repository specification is `docs/specifications/0002_CHAMPIONSHIP_LIFECYCLE_V1.md` **revision 7**, pushed at **`82d3823d7ce5a5e6a5626a28928b75d71b2d3b36`**. The primary rev7 implementation is in **`1d78ccc`**; the final acceptance/hardening delta described below is pending its closing commit at this handoff edit. Do not infer conformance from the older defended-title implementation commit `e75ebb7240b6253229142050d28eefba026a607c`.

Protected work units were created before implementation:

- `socr8s/private-ip#343`: permanent `(capability, unordered checkpoint pair)` title-match idempotence plus strict same-grade champion provenance.
- `socr8s/private-ip#344`: global archive+clear of **all** active champions and **all** active soups whenever holistic school identity changes.
- `socr8s/private-ip#345`: quarantine must not suppress complete valid championship contenders; replay the live silent-`12/12` cases.

The same authority has been written and read back in the canonical external records: Specs/Failures Ledger **S095-S098**, **ADR-A58/A59**, **F024-F027**; Curriculum Registry **Decisions 2026-10-19** plus new **Champion Lifecycle** rows; and the governing Google Doc amendment **CA-049 through CA-052 / OBS-16**. Old ledger rule S092 is explicitly marked superseded rather than deleted.

## Exact current championship rules

1. **One fight, period.** For one capability, two checkpoint SHAs may settle exactly one title fight in either direction for the lifetime of the run. Nothing changes that. Duplicate pairing is skipped before championship inference and cannot mutate owner, current score, surviving battery, or evidence. A different capability is a separate title and may have its own first-ever fight. Same-grade fan-out is one-hop, non-recursive, and skips settled pairs.
2. **Titles are grade-isolated.** Champion and contender checkpoint retained-update origin grade must equal the capability/title grade. Evaluation elsewhere does not relabel origin. Legacy cross-grade live owners are archived/inactivated, not grandfathered. Missing origin provenance fails closed. Individual champion advice is same-grade only; soups are the championship-derived cross-grade influence mechanism while geometry remains compatible.
3. **Quarantine is not a tournament-wide embargo.** A blocked capability may be withheld, but complete source-valid measurements for other same-grade capabilities still enter championship processing. A valid same-grade `12/12` must be able to open its first-ever pairwise title fight even if some unrelated capability is quarantined.
4. **Holistic school change clears everything active.** Active roles and soups are valid only under one exact championship school identity, bound at minimum to `course.digest()` / school-wide question inventory, semantic graph, parameter shapes/model geometry, and factory release. Any mismatch archives and clears **all** active roles and soups before advice/defense. Keep the causal student+own AdamW, immutable historical evidence, and permanent settled-match ledger. Do not selectively salvage or automatically re-score old active advisers.

## Live evidence explaining the apparently immortal step-125096 checkpoint

Read-only event reconstruction proves step **125096**, SHA prefix `60d3731d5435`, is **Grade-B origin**, not Grade-A origin. Grade A ended at step 125080; B teaching produced 125096. Under superseded cross-grade rules, a Grade-B MAIN/GENERALIZATION exam then minted all twelve A+B titles at once. Six current A slots were therefore legacy cross-grade contamination.

The old checkpoint also looked superhuman because the same step-125096 incumbent and step-127512 challenger were allowed to fight repeatedly. Each successful defense could refresh/grow the incumbent's surviving battery, creating an incumbent-selected ratchet with observed defense batteries such as A.EDGE 187/187 and A.LINK 227/227. Separately, genuinely new A-origin checkpoints later hit source-valid `12/12` capability-best scores but sometimes received **no championship decision at all**. Root cause is the current `_take_exam()` blanket championship bypass when `blocked_before` or `blocked_after` stagnation quarantine is active. Thus the old champ's apparent immortality is a mixture of real retained A knowledge and three policy defects: cross-grade incumbent contamination, duplicate-pair battery ratcheting, and suppression of valid contenders.

## 2026-10-19 source-edit / human-run overlap during rev7 implementation

The first human Prometheus process was deliberately stopped at generation 7330 / optimizer step 128424 before runtime edits began. During the implementation window, a **new human-owned** process was started externally at 04:45:59 local time while this working tree still had uncommitted source edits in progress. It was detected as PID 16874 and, under the already-established source-mutation safety authority, SIGTERM'd without further source mutation at durable generation **7488**, Grade A / MAIN, native AdamW step **128664**, student SHA **`d208dff428c7f7acc8497f69e66b929986069fc82189d369c7ecaf5bfca431d1`**. No agent started that neural process.

Because Python modules were imported while the working tree continued changing afterward, generations 7331–7488 are **HUMAN-RUN / SOURCE-IDENTITY-OVERLAP** evidence, not clean final-source qualification. They are still informative and must not be discarded: the human-started resume executed the neural-inert governance migration at generation 7331, backfilled **279** first-settled matchup identities, ignored **655** historical duplicate settlements, inferred **535** unambiguous checkpoint-origin records, globally reset all 12 legacy roles and A/B soups with zero optimizer updates, and then re-earned only six Grade-A roles from an A-origin step-128440 checkpoint. Across the 44 post-migration title settlements observed before stop, every pair was unique and none had a pre-7331 settlement. Treat that as supporting live-mechanism evidence only; final source conformance still requires the clean stopped-run/disposable validation below before any human resume.

## 2026-10-19 final acceptance checkpoint

A second externally started human trainer was detected while final source hardening was in progress. Source mutation stopped immediately; PID **45645** was SIGTERM'd and exited cleanly. The resulting durable boundary is generation **7594**, result `ACTIVE_GRADE_B`, stage `RECOVERY_2`, native AdamW step **128840**, student SHA **`fa11e7530aa0b4505461979bf35b62864d7e6936909246ec5fe432492e433fbe`**. The optimizer step and student SHA did not move during that overlap. Canonical stopped-run hashes after the graceful fence are `state.json` **`a117144a598b2fb9d3d967186f1b9e0dda5bd4ae6e72237d68e4d1e2a26d538d`** and `events.jsonl` **`3ae93204294dc115feda20180a344d3005839289a023119f6f55b8b34d0f5677`**. No agent started either human neural process.

After that fence, a fresh APFS COW clone of canonical generation 7594 was byte-identical to those two hashes. Direct `_resume(...)` was executed **twice** on the disposable clone. Both resumes were byte-no-ops: generation remained **7594**, student SHA remained `fa11e753...`, receipt and loaded native AdamW step remained **128840**, `state.json` and `events.jsonl` hashes did not change, checkpoint-origin evidence remained **551 proven / 0 ambiguous**, the permanent settlement ledger remained **356** entries, and current A/B authority remained 12 roles / two soups. This proves repeated-resume custody/idempotence under the final stopped-run evidence without optimizer movement or canonical mutation.

The rev7 eligibility floor is now explicitly separated by reset type. The strict-later-step floor remains enforced for the human-requested administrative empty-roster reset and experiment rebase paths. A holistic school-identity change archives+clears live authority but **preserves the epoch's existing floor** rather than inventing a new same-step embargo. Repeated holistic identity changes are explicitly tested: every changed identity can archive+clear authority again while preserving the permanent settlement ledger and prior archives. Archived checkpoint custody now permits legitimate different filenames for the same SHA only when optimizer-step/native-AdamW identity agrees; contradictory same-SHA identity still raises `MENTOR_EPOCH_CHECKPOINT_POINTER_CONFLICT`.

For #345, `scripts/audit_championship_quarantine.py` provides a read-only replay over immutable `events.jsonl` plus saved states. Before generation 7331 it finds **27 measured 12/12 contenders** that had no championship decision while quarantine was active or newly triggered. Because the legacy states have no persisted holistic championship identity, rev7 first fails closed into a global empty authority reset; the audit therefore conservatively classifies all 27 as `ROLE_MINT_AFTER_HOLISTIC_RESET` rather than pretending legacy incumbents survived that boundary. The strongest concrete fossil is generation **6692**, step **127512**, A-origin SHA `90698305...`: B.IFF was measured at 5/12 and became quarantined in that same generation, while A.EDGE/A.IDENTITY/A.LINK/A.MAPS/A.PARENT were each 12/12 and received zero championship decisions. The saved eligibility floor was 125080, below the challenger step. Thus five complete same-grade A contenders were silently suppressed by an unrelated post-score quarantine. The audit deliberately labels `NOT_MEASURED` only from explicit `withheld_capabilities`; old pre-repair history carries no such explicit withholding receipts, so it makes **zero** historical `NOT_MEASURED` claims. The repaired runtime and telemetry tests separately prove explicit withheld-vs-measured semantics, including that a capability newly quarantined after measurement remains measured and championship-eligible for that completed exam.

Current championship verification is green: **137** learning tests; **46** adjacent championship/operator/numeric/audit integrations; **32** Grade A/B/C system tests; focused championship bundles **38** tests; syntax compilation and `git diff --check` pass. Repo-wide `npm test` reports **760 total / 752 passed / 4 failures / 2 errors / 2 skipped**; every championship-related failure from the prior run is repaired. Remaining failures are unrelated current-branch debt: one `SourcePrefetchTests` broken process pool, two historical-ABI checks caused by widespread pre-existing scattered numeric literals, and three presentation table-width/layout assertions. `npm run quality:check` reaches `FACTORY_ARCHITECTURE_OK` then fails on the pre-existing `docs/images DOCS_TOP_LEVEL_DIRECTORY`; `npm run release:check` passes; `scripts/check_semantic_boundaries.py` passes. Do not misrepresent those baseline defects as a green whole repository, and do not expand #343-#345 to repair unrelated debt.

## Remaining closeout sequence

1. Complete independent read-only diff reviews for #343/#344 and #345; correct any material finding before commit.
2. Re-check no human trainer process is active, rerun the focused acceptance tests and diff hygiene after any review correction, then commit only the intended final hardening/audit/docs delta.
3. Push non-force and verify the exact remote SHA.
4. Update private issues #343-#345 with concrete test/live evidence and close only after remote readback. Leave #346 open, P1, assigned to `@crates`, and unimplemented.

---

# HISTORICAL: Championship repair installed (2026-10-18)

Governing private authority: **https://github.com/socr8s/private-ip/issues/336 (#336), verified OPEN**, IPR-0220. Source implementation **`7d879a9920df9fc3d987c485580c0e2885f8f7ea`**, developed on `codex/champion-ownership-20261018` and installed by local fast-forward on **`codex/0001-factory-cutover-20261018`**. This handoff is its documentation successor; use `git rev-parse HEAD` for that successor's identity. No push, main merge, release or issue closure occurred.

Current task checkout: `/Users/emilie/Code/bilqis-mlx-retention-lab`. Actual run: `runs/codex-0001-prometheus`, ID `a1cc702b3fea47ec9f9da9265529f9ba`. These task-specific source/run bindings supersede the historical continuation instructions below.

Implemented and independently reviewed: normal fresh runs earn capability roles from complete relevant-grade exams before graduation. Weaker replays preserve titles and votes; challengers must beat current identical-cohort incumbent scores. Equal-max ties use grade-local simultaneous perfect breadth; full-grade ties require strict complete-school victory against every displaced owner from any contender origin. Every external winner correctly answers all earning questions, including misses, from every displaced champion and ancestor across all their roles. The winner absorbs every lineage branch. A failing branch blocks the entire equal-max grade takeover. Append-compatible historical checkpoints compete only on complete readable grade panels; partial school evidence cannot certify school takeover. Historical max-question proof preserves voting entitlement. Candidate retention, teacher policy, graduation and flash behavior remain unchanged.

Proof: **121/121 focused tests passed, zero failures/skips**, including disposable native-MLX integrations and the lineage/prefix regressions. Factory architecture, docs, release consistency and diff checks passed. Independent review found no remaining critical blocker after fixing atomic branch transfer and compatible-prefix scoring. Broader suite: 679 total, 673 passed, 4 failed, 2 skipped; all four failures reproduced on untouched base `19df4892ae8dfd278ee40b4f3de9d01becf8b393` (two historical-ABI scan tests and two imports referencing relocated `tests.test_grade_c_trainer`). The smell audit adds zero findings against that base but retains three pre-existing findings. These are unresolved baseline defects, not a green full-suite claim.

Installation held the stopped run's actual `.grade-a-operator.lock`. Read-only `npm run train -- --dry-run --resume --verify-source --run-dir ./runs/codex-0001-prometheus` passed. Saved generation **3662**, native AdamW step **123192**, student/AdamW tensor SHA **`0e966b12c77476f1500da96f8bb09787efe339557dd3d5e2270ae658036bcb19`** stayed unchanged. State, event ledger, current bundle/manifest/catalog hashes and all **2,607 run-file size/mtime entries** matched before and after. Receipt: `/Users/emilie/.codex/validation-logs/20261019-championship-install-7d879a9.json`; complete preflight: `/Users/emilie/.codex/validation-logs/2026-10-19T03-35-50-257Z-80371.log`.

Incident **PM-2026-10-18-008**, RC-031/PAT-079, records the fresh-run wiring defect, the corrected current-score interpretation and Highlander obligations in the canonical Entif Post-Mortem Ledger. Neural improvement and the next actual title election remain unobserved. Uncaptured historical champion weights were not recovered or synthesized. Only the human may start/resume actual optimizer updates; the next permitted action is a human normal non-flash resume, whose next complete grade exam can establish roles. Agents may inspect evidence and run read-only preflights or disposable tests. Preserve student, own AdamW, teacher, source/oracle, token ABI, old checkpoints and all receipt history.

---

# Canonical checkout continuation (2026-10-17)

The single active checkout is `~/Code/bilqis-mlx`, branch `codex/canonical-mlx-release-20261017` while the v0.2.0 release is prepared. The former experimental code through `2098458` and Finder metadata bug fix are incorporated. The 4,361-file current student clone from the experimental run was individually SHA-256 verified, promoted to `runs/school-mlx-v1/` at generation 8390, optimizer step 223256; the former run was retained as `runs/archive/pre-parity-school-20261017/`. This is no reset and no recreation of the source student. Subsequent live optimizer steps occur only in the human-launched canonical run and must be inspected directly. External inherited source dependencies are vendored under `vendor/legacy-v16/` with their source hashes preserved. The only mounted purported external drive was a read-only disk image, not an archive destination. There has been no deletion of old worktrees/checkpoints, no NAS copy and no tag/release verified at this writing. See `docs/operations/CANONICAL_REPOSITORY_AND_RELEASE_20261017.md` for exact verification and outstanding tasks. **The instructions and stale paths below are retained as historical handoff provenance; the paragraph above and current README supersede their location and run-command assumptions.**

---

# Bilqis numeric staircase | continuation handoff

**User reports immediate improvement after the change.** Keep working prototype-first: fail fast, thin vertical slices, incorporate feedback, defer research qualification/deconstruction. Observe this run before choosing another change. Do not restart learning or introduce new gates.

## Source and authority

- Worktree: `/Users/emilie/.codex/worktrees/ff64/bilqis-mlx`.
- Private branch: `codex/336-evergreen-factory`; implemented/pushed/remote-verified source **`ed5bb9f4a2ab535226f984df9ea01e3995085e52`**. This handoff is a documentation successor; use `git rev-parse HEAD` for its final commit.
- Governing **https://github.com/socr8s/private-ip/issues/336 (#336), OPEN**, parent #335 / IPR-0220; private implementation `Entif-AI/bilqis-mlx#1` remains open. Read current issue and source comments `6233567989`, `6234081376`; implementation checkpoint: https://github.com/socr8s/private-ip/issues/336#issuecomment-6237402961 . ADR-041 governs prototype-first scope; ADR-044 records this staircase.

## Implemented and verified

`numeric_staircase.py` reuses existing C AST/generator and checkpoint/generation/outbox owners. Introduce COUNT → NUMBER → SUCCESSOR → ADD → SUB at **0..3**, then master those five at **0..4**, **0..5**, **0..6**, then introduce **MUL → DIV**. All five must be perfect at the same current checkpoint before each scope increase. Existing adaptive teacher, A/B recovery and final A→B→C replay remain active. Stop expansion at 6.

Human `--resume --numeric-staircase` enrolls once; subsequent resumes detect the mode. All 227 embedding rows remain allocated; no parameter growth or rollback. Each scope gets a fresh fixed exam; old results remain historical. Wider unresolved mistakes remain deferred, and the complete pre-staircase checkpoint remains pinned.

The 92-case focused suite and hosted CI passed, as did semantic-boundary/ABI checks (independent expected ABI SHA remains advisory/unconfigured). A disposable actual-run copy recovered interrupted enrollment and repeated resume with all parameters/AdamW moments identical, teacher/champions/soups/bests preserved and actual files unchanged. Receipt: `docs/evidence/experiments/20261017-numeric-staircase-resume.json`. Toy transition tests use mocked predictions, not learned mastery. Python: `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`; selected school tests need `PYTHONPATH=.:tests`. Use the validation-output runner for finite checks.

## Human has resumed actual training

Run: `/Users/emilie/Code/bilqis-mlx/runs/school-mlx-v1`.
Read-only snapshot on 2026-10-17: generation **7151**, step **207768**, staircase release `bilqis.mlx.numeric-staircase/20261017-v1`, integer maximum **3**, introduction stage **3** (through ADD), phase `RECOVERY_1`. Queue: `B.NOT`, `A.MEMBER`, `B.AND`.

Complete student: `bundles/best-5688-2b8c050558c9`, SHA **`42d1741948fc37e5da8b74e28098c178a66441afbb0b6a35fad186e7d36174a3`**, with matching native AdamW. Latest same-checkpoint C scores: COUNT **11/12**, NUMBER **9/12**, SUCCESSOR **10/12**, ADD **9/12**. A/B scores range 8–12/12, so recovery remains relevant. This is a moving snapshot; reread before acting. The user's immediate-improvement report is encouraging feedback, not a measured before/after comparison.

## Next action and boundaries

Inspect current state/events and the next useful learning/retention result; discuss or implement the smallest warranted adjustment. Do not interrupt the human run or hot-edit its source. Only the human starts/resumes actual `--human-run`; agents may inspect and test disposable copies. Preserve complete FP32 student, own AdamW, teacher policy/history, champions/soups, stable tokens, original artifacts and 100 GiB reserve.

Unfinished: neural undefined-division answer (symbolic 0/0 and nonzero/0 tests already exist), 7..10 experiments, generic cutover/outcome machinery, research qualification. Defer these unless the next observation warrants them. D remains unselected.

Related incidents: **PM-2026-10-17-003**, RC-095/096/097, PAT-076; C-source **PM-2026-10-17-002**; teacher boundary **PM-2026-10-14-014**. No new incident, merge, public publication or issue closure in this handoff. Keep protected references private.
