# Bilqis-MLX #31–43 Pro launch preflight (2026-10-24)

Status: operational handoff evidence only. This document does not amend the governing issues, specs, or repository authority.

## Target and scope

Repository: `Entif-AI/Bilqis-MLX`. Work in an isolated worktree branched from verified `origin/main`, not the unrelated `Entif-AI/Bilqis` checkout. Verify the exact Git remote and worktree writer before editing. Preserve existing trainer/checkpoints and human-only neural update authority. Read `AGENTS.md`, #19, and each issue's own complete current execution contract with its parent and dependencies before implementation.

Primary sequence: #31, #32, #33, #34, #35, #36, then #37, #38, #39, #40, #41, #42, #43. Treat this as a preference constrained by the dependencies below.

## Dependency frontier

- #31: stable IRI grammar (parent #20, root #19).
- #32: SKOS resource shapes (depends #19).
- #33: Unicode notation datatype rules (parent #20).
- #34: label/documentation mapping (parent #20).
- #35: SKOS semantic relation and extension boundary (parent #20).
- #36: cross-scheme mapping strength rules (parent #20).
- #37: CSV preflight (depends #20 profile closure).
- #38: identity resolution (depends #31, #32, #37).
- #39: public source references (depends #37, #38).
- #40: SKOS graph output (depends #32, #33, #34, #38, #39).
- #41: deterministic canonical digest (depends #40).
- #42: explicit held/error ledger (depends #35, #36, #37, #38).
- #43: reproducible build entrypoint (depends #37, #38, #39, #40, #41, #42).
- #20 parent closure requires all six of #31–36 to close with evidence. #21 parent closure requires #37–43. Do not confuse code written on a branch with an accepted/merged requirement.

Optional issues selected by user: #45, #53, #57, #59, #60, #62, #71, #73, #75. #62 needs only #36; #57 needs #35 and #21; #45 additionally needs #44; #53 needs #50–52; #59 needs #45; #60 needs #56–59; #71 needs #48/#55/#61/#66/#69; #73 needs #43/#72; #75 needs #74. Respect all external blockers and reconsider each live issue before uptake.

Source corpus: `lib/ithkuil/_data/csv/` in the correct repo. Source/relational IR, semantic identity, canonical RDF, held rows, FalkorDB-derived state and curriculum execution are distinct authority planes. Deterministic builds may not call an LLM. No protected source paths, credentials or private authority content in this public repository.

## Execution and recovery

Use user-selected Entif Architecture, BIOS Runtime durability/continuity, and Entif Work Stack as scoped. Git provides durable checkpointing for a persistent local worktree. Use Work Stack for the dependent issue sequence and external side-effect reconciliation. The project has no root-local Work Stack helper; the live Skill owns its canonical implementation. Revalidate scripts and paths in the executing session. A working preflight helper snapshot exists at `/Users/emilie/Code/.entif-proof-runtime/bilqis-mlx-pro-20261024/tools` and should not be treated as repository source authority.

For each issue: hydrate issue/parent/direct dependency from live GitHub; verify readiness; perform smallest complete implementation; positive and negative tests and deterministic/fresh-state checks as applicable; commit/push non-force to the owned feature branch; read remote SHA; stage PR/review evidence and issue checkpoint with exact refs. Reconcile uncertain mutations before retry. Never force-push, reset another writer, directly push main, or start real neural training. Keep one complete issue checkpoint before advancing to the next. On session truncation emit precise handoff: branch/worktree/head, issue, committed tasks, blockers, tests, failed attempts, next legal step, and Work Stack path.

Merge and issue-close authority must be established by the user or governing standing policy. A passing PR or unmerged commit does not alone close #20/#21 dependencies.

Preflight GitHub R/W fixture: this branch was created through the connected GitHub tool from `main`; this file is intentionally placed on the isolated preflight branch and must not be mistaken for a mainline requirement.
