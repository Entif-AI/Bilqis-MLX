# CURRENT: championship conformance repair queued after durable authority capture (2026-10-19)

**Read this section first. It supersedes conflicting championship instructions below while preserving them as history.**

Current worktree: `/Users/emilie/Code/bilqis-mlx-retention-lab` / `/code/bilqis-mlx-retention-lab`. Branch: `codex/0001-factory-cutover-20261018`. Active human run lineage: `runs/codex-0001-prometheus`. Only the human may start/resume real neural optimizer work. Before any source mutation, re-check for an active human trainer and refuse to hot-edit a running process.

Current governing repository specification is `docs/specifications/0002_CHAMPIONSHIP_LIFECYCLE_V1.md` **revision 7**, pushed at **`82d3823d7ce5a5e6a5626a28928b75d71b2d3b36`**. The implementation for the 2026-10-19 corrections is **NOT YET COMPLETE**. Do not infer conformance from the older defended-title implementation commit `e75ebb7240b6253229142050d28eefba026a607c`.

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

## Next safe execution sequence

1. Commit/push/read back this documentation/governance checkpoint, including ADR-069/070, this HANDOFF, and the scoped AGENTS/README amendments. Do **not** include unrelated or premature implementation edits merely to make the tree clean.
2. Re-check active trainer/process custody immediately before implementation source mutation.
3. Add/finish focused failing regressions for settled-pair idempotence, same-grade origin, global school-identity reset, and quarantine-independent contender admission.
4. Implement a durable settled-match ledger, checkpoint-origin provenance, deterministic championship school identity, lossless global role/soup reset, and capability-local quarantine/title routing.
5. Backfill/migrate from durable run events fail-closed. Read-only replay against Prometheus must show that legacy B-origin A authority is inactive and prior settled pairs cannot rematch without modifying neural state.
6. Run focused and widened suites, commit only intended files, push non-force, verify exact remote SHA, update external ledgers/issues and protected session minutes with actual proof.

There are currently uncommitted TDD scaffolds in `bilqis_mlx/learning/tests/test_epoch_championships.py` begun before the user's durability interruption. They are **not implementation proof** and must be reviewed against the now-durable revision-7 contract before continuation. Root `AGENTS.md` and `README.md` also contain uncommitted policy edits and still need the holistic-reset clause integrated before the documentation checkpoint.

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
