# BAMF-0.2 legacy trainer adaptation authority

Effective: 2026-11-07

This file distinguishes historical learner evidence from the current legacy
trainer source that successor issues may inspect and adapt.

## Current adaptation oracle

Any BAMF issue, remediation, compatibility task, EGM review, or worklog that needs
the **latest legacy trainer** MUST use:

- worktree: `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026`
- branch: `codex/337-replay-349-20261026`
- run: `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`
- state head: `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay/state.json`

Before treating legacy behavior as an implementation premise, run:

`python3 -B scripts/check_legacy_trainer_authority.py --live`

The command is read-only. It verifies the preserved worktree/branch identity, run
directory and state-head shape, then prints the observed Git head and run
generation so the worklog can cite what was actually inspected.

## Prometheus boundary

Prometheus is historical evidence, not the current legacy-trainer adaptation
oracle. `runs/codex-0001-prometheus` may still be cited when the historical
Prometheus lineage itself is the subject. It MUST NOT be used to infer the latest
legacy trainer's policy, scheduler, teacher, resume semantics, state shape, or
compatibility contract.

The repository deliberately retains Prometheus-specific ADRs and convenience
commands because they describe or operate that historical lineage. Their presence
does not supersede this adaptation-source rule.

## Mechanical enforcement

`scripts/check_legacy_trainer_authority.py` validates this declaration and scans
current BAMF task/evidence surfaces for the stale Prometheus run path, ambiguous
Prometheus-as-current-baseline language, and legacy-trainer worklogs that omit the
canonical `microspenics-349-replay` source. Static validation runs in normal quality
checks. `--live` adds the local preserved-run identity proof and is required before
legacy-derived implementation or review work.
