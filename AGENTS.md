# Bilqis MLX | Agent operating rules

Authority: user's latest directives, protected `IPR-0220`, `ADR.md`, and approved issue #1. Implementation is **private**; public Bilqis #160/#162 receive screened summaries only.

- Start by reading `README.md`, this file, `ADR.md`, `HANDOFF.md` and current issue/branch. Before editing shared root docs, reread each, apply narrow concurrent-safe updates, and inspect the diff. `ADR.md` is append-only; `HANDOFF.md` is current-state only.
- Keep historical FP32 student, its original AdamW, frozen semantic graph/token IDs, old worktrees and candidate archives unchanged. New Ithkuil semantics are versioned mappings/new nodes, **never rewrites of old primitives**.
- Old `G##` and `B##` are archived capability aliases. New grades are A, B, C... with approximately 6–9 similar-level capabilities each. Grade mastery requires one intact same-checkpoint model+optimizer at 100% on its complete grade rubric.
- Complete one full active-grade pass, then two freshly ranked weakest-three recovery rounds across active + all previously passed grade capabilities, then repeat. An earlier champion checkpoint casts one vote per represented grade. Soups are frozen teachers, not trainable students.
- Never test untaught roots or compose tests before separate prerequisite mastery in earlier grades. Teach appropriate binary and finite typed answers. Source attest all lessons and independent oracles; if evidence is absent, block advancement rather than guessing.
- Agent-run dry-runs, tests, read-only parity, dashboard/status, and safe fixture experiments are authorized. **No agent-run neural optimizer updates to actual Bilqis students.** Keep real training disabled until qualified for human launch.
- Reuse six-panel School50 and stable npm commands. Protect disk headroom; no recursive cleanup of `~/Code`, no archive deletion, no model binaries in Git. Backup only explicit source paths with external readback evidence.
- Run tests, inspect diffs, confirm writer coordination and push only a private feature branch with remote readback. Do not force-push, mutate main, or publish protected algorithms.
