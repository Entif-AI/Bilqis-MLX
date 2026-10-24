# TASK-0003: Execute the issue #150 factory micro-spec workstack

**Parent:** `Entif-AI/Bilqis-MLX#150`.
**Authority:** SPEC-0001 + SPEC-0005 + the leaf specification selected by the workstack.
**Mutation posture:** implementation only after the current issue page and its named direct prerequisites authorize execution.
**Neural authority:** this task never authorizes a real `--human-run` neural update.

## Goal

Execute authorized factory-architecture leaves sequentially without re-researching
or redesigning settled architecture. The workstack fixes the reusable factory. It
does not create or execute one issue per future semantic root.

## Bootstrap once

At the start of each fresh execution session:

1. verify the intended branch/worktree, local and remote heads, and writer-coordination state; stop on unexpected mutation;
2. verify no human-owned `bilqis_mlx.cli train --human-run` process owns the source tree;
3. read root `README.md` and `AGENTS.md` once before source mutation, then read the broad factory authorities needed for the current bounded task;
4. bind any run-specific authority receipt to the exact branch/base and the selected issue or amendment when required by that contract.

The workstack manifest remains a grooming and architecture-maintenance index. It
does not authorize an ordinary leaf run to hydrate the parent issue, the complete
manifest, all leaf receipts, or a global ready set. Do not reread broad authorities
between pages unless authority changes or the next page explicitly requires it.

Keep a healthy warm model session across cold issue-page boundaries. A cold page
means reading the next issue's own gate and contract; it does not require a new
expensive model session. Start fresh only after actual context failure or
compaction pressure. The current issue number is the durable bookmark; Git and
GitHub receipts are execution state, and model context is cache.

## Page-local issue navigation

The live `FACTORY_PAGE_GATE_V1` on the bookmarked issue controls page order. Read
only that issue, its later same-page amendments, its named direct prerequisites,
and the files declared by the leaf contract. Do not inspect #150, the whole
manifest, unrelated leaves, or all receipts during ordinary page execution.

Interpret the current page's latest terminal state locally:

- `FACTORY_LEAF_DONE`: do not rerun the leaf; follow its `next_page`.
- `BLOCKED_SPEC_GAP`: execute only when a newer same-page
  `FACTORY_SPEC_AMENDMENT_V1` has `reopen: true`; otherwise follow `next_page`.
- `FACTORY_DEPENDENCY_BLOCKED`: this is a staleable observation, not a permanent
  terminal. Recheck only the named direct prerequisites. No same-page amendment
  is required merely to reevaluate dependency state. If a prerequisite still
  blocks the leaf, retain the specific blocker and follow the page gate; if all
  prerequisites are satisfied, execute under the frozen leaf contract.

For each direct prerequisite, use only its latest local execution state and its
own page gate when that state requires a revisit. Do not reconstruct or recompute
the global ready set. When a page completes or remains blocked, follow its
explicit `next_page` and treat prior-page context as non-authoritative except for
commit or receipt references named by the new page.

## One-leaf execution loop

For each leaf whose live page gate and direct prerequisites authorize execution:

1. read the leaf spec;
2. read only its GitHub issue, page gate/amendments, and named direct prerequisites' latest local receipts;
3. read only files and symbols in the spec's read allowlist;
4. confirm the actual named symbols still match the spec's assumptions;
5. implement only the predetermined design inside the write allowlist;
6. preserve every compatibility/wire/error contract named by the spec;
7. run the leaf's exact focused proof commands;
8. inspect the diff and `git diff --check`;
9. create one leaf-scoped commit where practical;
10. refetch before push, push normally without force, and read back the remote SHA;
11. post and read back one issue receipt;
12. follow the issue's explicit `next_page`; do not recompute a global ready set.

A successful issue receipt uses this shape:

```text
FACTORY_LEAF_DONE
spec_id: SPEC-####
bootstrap_sha256: <run authority hash>
spec_sha256: <exact spec hash>
issue_sha256: <exact issue-body hash>
commit: <remote SHA>
work_completed: <bounded summary>
proof: <commands and results>
work_not_completed: none
blockers: none
unresolved_questions: none
```

If there is optional follow-up outside the leaf's invariant, name it under
`work_not_completed` but do not pretend the leaf is incomplete when its own contract
is fully proven.

## Block instead of researching architecture

If a leaf assumption is materially false and the fix is not already decided by the
spec, do not broaden the read set or design a new architecture in the execution run.
Post:

```text
BLOCKED_SPEC_GAP
spec_id: SPEC-####
bootstrap_sha256: <run authority hash>
spec_sha256: <exact spec hash>
issue_sha256: <exact issue-body hash>
reason_code: MISSING_CONTRACT|UNDECLARED_DEPENDENCY|SURFACE_ESCAPE|PROOF_GAP|AUTHORITY_CONFLICT
failed_assumption: ...
observed_fact: ...
required_decision: ...
required_read_authority: ...
required_write_authority: ...
proof_attempted: ...
```

Then follow the issue's explicit `next_page`. Do not recompute a global ready set;
continue only when the next page's local gate authorizes it.

## Exploration prohibitions

During ordinary leaf execution do not:

- broadly explore the repository;
- run unrestricted `rg` across the tree;
- hydrate parent issue #150, the full workstack manifest, all receipts, or a global ready set;
- search Git history for architecture archaeology;
- search all GitHub issues for alternatives;
- browse the web for a different design;
- create new abstractions not authorized by the leaf;
- preserve an obsolete API merely to avoid migrating its bounded callers;
- invent semantic-root tickets to keep the run busy;
- start neural training.

Exact-reference checks explicitly required by a leaf, such as proving that a legacy
symbol has no remaining callers before deletion, are allowed and must remain narrowly
scoped to the named symbol/path family.

## Verification cadence

Run only leaf-focused verification after an ordinary leaf. At a wave boundary, run
the wave's package/conformance/architecture gate. Run the full repository suite only
at terminal closure or when a leaf explicitly requires it.

Never claim neural learning, generalization, or student progress from this workstack.
