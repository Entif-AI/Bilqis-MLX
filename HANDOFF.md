# Bilqis evergreen factory | warm-start numeric staircase

## Authority and current source

Governing **https://github.com/socr8s/private-ip/issues/336 (#336), OPEN**, parent #335 / IPR-0220. Private implementation issue `Entif-AI/bilqis-mlx#1` remains open. User source comments `6233567989` and `6234081376` remain binding alongside the latest prototype-first direction. The human now requests pausing C, continuing the latest student without rollback, and implementing their smaller staircase; they explicitly chose **Start at 0–3**. ADR-044 supersedes ADR-043's future-experiment disposition.

Worktree `/Users/emilie/.codex/worktrees/ff64/bilqis-mlx`, private branch `codex/336-evergreen-factory`. Verified baseline HEAD **`babe284d0c98a24fcd4010ecce61f7db4ee152bf`**; this increment's final SHA belongs in the protected issue checkpoint. Prior native-C integration was `34b083f4a5d0ed6fcf647f8612ba42c8e2417852`.

## Implemented behavior

Human opt-in `--resume --numeric-staircase` enrolls release `bilqis.mlx.numeric-staircase/20261017-v1`: COUNT → NUMBER → SUCCESSOR → ADD → SUB at 0..3; require all five perfect at the current complete checkpoint, then master 0..4, 0..5 and 0..6 individually; introduce MUL, then DIV at 0..6. Existing adaptive teacher and A/B recovery remain active. The existing school performs A→B→C replay before further advancement. Scope stops at 6; 7..10 comparison experiments remain later choices.

`numeric_staircase.py` composes existing C source semantics/generator and checkpoint/generation/outbox owners. No existing constructor/source admission bytes or catalog identities changed. All 227 embedding rows stay allocated; parameter shapes stay fixed. Each scope receives a fresh enrollment exam, fixed through failures in that scope. Previous exams and enrollment states remain historical; old mastery does not qualify the new scope. Wider unresolved mistakes are retained and deferred. The pre-staircase complete checkpoint is pinned against pruning. Normal subsequent resumes automatically reconstruct the saved scope.

## Paused actual student and proof

The trainer had already exited when its PID was checked during the requested pause; no signal was sent. No actual enrollment migration or neural updates were performed by the agent. Actual run `/Users/emilie/Code/bilqis-mlx/runs/school-mlx-v1` remains on its old C release and 0..10 scope until the human opts in.

Observed generation **7081**, optimizer step **206968**, bundle `bundles/best-5638-939ffb9a3395`, complete student SHA **`f8d179c673eb04c9b79524a09fd6611c53a771155360007314c28e4898345470`**. Model: 227 tokens, width 384, six layers, 10,745,856 parameters.

An independent APFS copy recovered interrupted staircase enrollment and repeated resume with every parameter/AdamW moment identical, matching optimizer step, teacher/champions/soups/bests unchanged, and previous enrollment intact. All five actual saved-file hashes stayed unchanged. Result: `docs/experiments/20261017-numeric-staircase-resume.json`. Real-run CLI dry-run reports no blockers. The 92-case affected numeric/operator/A-B-C-trainer/lifecycle/school suite passed; semantic-boundary and historical-ABI checks passed (external expected ABI SHA remains unconfigured/advisory). Some school tests require `PYTHONPATH=.:tests` when selected by module. Python: `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`.

The full disposable staircase test mocks source-gold predictions to exercise transitions; it does not report learned mastery. Real learning and retention under the new ordering remain to be observed. Symbolic boundary tests cover 0/0 and nonzero/0; an explicit neural undefined-answer output is deferred. The optional Q01–Q10 qualification dossier still reports missing research-evidence receipts; ADR-041 defers that work for this prototype. Generic cutover/outcome machinery remains incomplete and unused. No new research infrastructure is the next task.

## Next permitted action

The human may run the README command from this worktree with `--human-run --resume --numeric-staircase`, explicit actual run/source paths, and the ordinary 90-minute duration. There is no implicit visit cap. Later resumes may omit the staircase flag. Agents may inspect actual state and exercise disposable models, but never start/resume actual neural updates.

Preserve complete FP32 student and own native AdamW, teacher policy/history, champion/soup pointers, stable token IDs, immutable original artifacts and 100 GiB reserve. Related incident **PM-2026-10-17-003**, RC-095/096/097, PAT-076; C-source PM-2026-10-17-002 and teacher-boundary PM-2026-10-14-014 remain relevant. No new incident exercise, merge, public publication or issue closure is part of this increment. D remains unselected. Keep rapid useful trials as the governing priority.
