# Bilqis numeric staircase | continuation handoff

**User reports immediate improvement after the change.** Keep working prototype-first: fail fast, thin vertical slices, incorporate feedback, defer research qualification/deconstruction. Observe this run before choosing another change. Do not restart learning or introduce new gates.

## Source and authority

- Worktree: `/Users/emilie/.codex/worktrees/ff64/bilqis-mlx`.
- Private branch: `codex/336-evergreen-factory`; implemented/pushed/remote-verified source **`ed5bb9f4a2ab535226f984df9ea01e3995085e52`**. This handoff is a documentation successor; use `git rev-parse HEAD` for its final commit.
- Governing **https://github.com/socr8s/private-ip/issues/336 (#336), OPEN**, parent #335 / IPR-0220; private implementation `Entif-AI/bilqis-mlx#1` remains open. Read current issue and source comments `6233567989`, `6234081376`; implementation checkpoint: https://github.com/socr8s/private-ip/issues/336#issuecomment-6237402961 . ADR-041 governs prototype-first scope; ADR-044 records this staircase.

## Implemented and verified

`numeric_staircase.py` reuses existing C AST/generator and checkpoint/generation/outbox owners. Introduce COUNT → NUMBER → SUCCESSOR → ADD → SUB at **0..3**, then master those five at **0..4**, **0..5**, **0..6**, then introduce **MUL → DIV**. All five must be perfect at the same current checkpoint before each scope increase. Existing adaptive teacher, A/B recovery and final A→B→C replay remain active. Stop expansion at 6.

Human `--resume --numeric-staircase` enrolls once; subsequent resumes detect the mode. All 227 embedding rows remain allocated; no parameter growth or rollback. Each scope gets a fresh fixed exam; old results remain historical. Wider unresolved mistakes remain deferred, and the complete pre-staircase checkpoint remains pinned.

The 92-case focused suite and hosted CI passed, as did semantic-boundary/ABI checks (independent expected ABI SHA remains advisory/unconfigured). A disposable actual-run copy recovered interrupted enrollment and repeated resume with all parameters/AdamW moments identical, teacher/champions/soups/bests preserved and actual files unchanged. Receipt: `docs/experiments/20261017-numeric-staircase-resume.json`. Toy transition tests use mocked predictions, not learned mastery. Python: `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`; selected school tests need `PYTHONPATH=.:tests`. Use the validation-output runner for finite checks.

## Human has resumed actual training

Run: `/Users/emilie/Code/bilqis-mlx/runs/school-mlx-v1`.
Read-only snapshot on 2026-10-17: generation **7151**, step **207768**, staircase release `bilqis.mlx.numeric-staircase/20261017-v1`, integer maximum **3**, introduction stage **3** (through ADD), phase `RECOVERY_1`. Queue: `B.NOT`, `A.MEMBER`, `B.AND`.

Complete student: `bundles/best-5688-2b8c050558c9`, SHA **`42d1741948fc37e5da8b74e28098c178a66441afbb0b6a35fad186e7d36174a3`**, with matching native AdamW. Latest same-checkpoint C scores: COUNT **11/12**, NUMBER **9/12**, SUCCESSOR **10/12**, ADD **9/12**. A/B scores range 8–12/12, so recovery remains relevant. This is a moving snapshot; reread before acting. The user's immediate-improvement report is encouraging feedback, not a measured before/after comparison.

## Next action and boundaries

Inspect current state/events and the next useful learning/retention result; discuss or implement the smallest warranted adjustment. Do not interrupt the human run or hot-edit its source. Only the human starts/resumes actual `--human-run`; agents may inspect and test disposable copies. Preserve complete FP32 student, own AdamW, teacher policy/history, champions/soups, stable tokens, original artifacts and 100 GiB reserve.

Unfinished: neural undefined-division answer (symbolic 0/0 and nonzero/0 tests already exist), 7..10 experiments, generic cutover/outcome machinery, research qualification. Defer these unless the next observation warrants them. D remains unselected.

Related incidents: **PM-2026-10-17-003**, RC-095/096/097, PAT-076; C-source **PM-2026-10-17-002**; teacher boundary **PM-2026-10-14-014**. No new incident, merge, public publication or issue closure in this handoff. Keep protected references private.
