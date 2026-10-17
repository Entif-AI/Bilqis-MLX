# Bilqis evergreen factory | prototype-first continuation

## Latest direction

The human's 2026-10-17 correction governs: one person working at home with $50/month wants rapid experiments in novel learning and self-optimization. Build a small working trial, inspect useful learning/retention, then keep, revise or discard it. ADR-041 supersedes the prior qualification-first next actions. Independent outcome attestations, causal proof, exhaustive qualification and a generic cutover framework are deferred for exploration. Basic answer correctness and checkpoint recovery remain necessary.

## Current source

- Governing **https://github.com/socr8s/private-ip/issues/336 (#336), OPEN**, parent #335 / IPR-0220; private implementation issue #1 remains open. Preserve protected material privately. Latest human correction supplements source comments `6234271928`, `6233567989`, `6234081376` and supersedes the next-action priorities in checkpoint `6235720415`.
- Worktree `/Users/emilie/.codex/worktrees/ff64/bilqis-mlx`, branch `codex/336-evergreen-factory`. Verified starting HEAD **`37a42adf2669883dcb4d8e3f7ac807eb04742512`**, prior implementation **`f14b90dc82153555b4d9d365f21580667368db0e`**. This trial increment follows that head; its final SHA belongs in the issue checkpoint.
- Prior source result: **466 passed, 2 skipped**; source CI `39044710480`, documentation CI `39044894248`. This increment passed 24 focused integer/typed-answer tests plus semantic-boundary and historical-ABI checks; no full-suite rerun. Local ABI expectation remains advisory when independently unconfigured. Python: `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`.
- Implemented finite domains, construction contracts, witness checks and optional verification consumer remain available. The cutover planner performs no I/O and has no executor; selection comparisons are unused by the live trainer. Do not spend the next increment completing them.

## Completed thin slice and next step

Reused `integer_learning_smoke.py`, the existing integer/arithmetic AST generator and native typed-answer training adapter. `--trial` runs simple → composed → score-selected recovery, with fresh seeded constructions per optimizer step and fixed, instruction-eligible probes. `--operation ADD` narrows the existing generator by source operator; no grade-specific constructor or actual teacher-policy change was added.

Two 300-step disposable trials took about 29 seconds each. The broad arithmetic trial stalled at 16/37 simple and 29/43 composed answers after recovery. Narrowing to ADD reached 7/10 simple and 39/70 composed after two visits; the score-selected extra composed visit reached **60/70**, with simple retained at **7/10**. Predictions and gold counts are saved in `docs/experiments/20261017-disposable-integer-trial.json`. These scores use actual numeric semantic-token identities competing across all 222 historical tokens, with assertion scores recorded separately.

Repeat: `npm run curriculum:learning-smoke -- --trial --operation ADD --steps 100` using the M3 Python above. Keep the ADD slice and target remaining wrong numeric answers, including zero, before widening it. The newer generic candidate compiler is still Boolean-result-only; the trial uses the existing numeric path rather than expanding that compiler first. No generic cutover executor is required for this trial.

The ten questions guide selection; scale their consideration to this small trial. Research gaps outside the selected slice are deferred work. Incorrect gold, mismatched token/output identities and unrecoverable state are actual defects to fix. Do not silently bypass live admission checks: C's native Registry/output integration and selection-review checks remain unchanged in code. D is unselected. A disposable trial does not require admitting either grade.

## Actual student and recovery boundary

The last verified actual run `/Users/emilie/Code/bilqis-mlx/runs/school-mlx-v1` was generation **6824**, optimizer step **204072**, `AWAITING_NEXT_GRADE`, with historical human cumulative A+B **144/144**. These are prior observations, not a new live inspection. Custody receipt: `docs/EVERGREEN_SOURCE_ONLY_CUSTODY_20261017.json`; detailed prior tests: `docs/EVERGREEN_CONTRACT_QUALIFICATION_20261017.json`.

Only the human starts/resumes actual neural updates with `--human-run`. Preserve the complete student and own native AdamW, teacher, token identities, original artifacts, champion/soup pointers and 100 GiB reserve. Existing related incident **PM-2026-10-17-003**, RC-095/096/097, PAT-076; C-source PM-2026-10-17-002 and teacher-boundary PM-2026-10-14-014 remain relevant. No new incident exercise is required to begin a small disposable trial. Only fresh disposable models received optimizer updates. No actual-student training, merge, issue closure or public publication occurred.
