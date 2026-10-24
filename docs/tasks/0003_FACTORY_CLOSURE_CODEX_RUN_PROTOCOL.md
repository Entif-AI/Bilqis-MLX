# TASK-0003: Execute the issue #150 factory micro-spec workstack

**Parent:** `Entif-AI/Bilqis-MLX#150`.
**Authority:** SPEC-0001 + SPEC-0005 + the leaf specification selected by the workstack.
**Mutation posture:** implementation only after the manifest is execution-ready.
**Neural authority:** this task never authorizes a real `--human-run` neural update.

## Goal

Execute as many ready factory-architecture leaves as possible sequentially without
re-researching or redesigning settled architecture. The workstack fixes the reusable
factory. It does not create or execute one issue per future semantic root.

## Bootstrap once

At run start:

1. verify the intended branch/worktree and current writer-coordination state;
2. verify no human-owned `bilqis_mlx.cli train --human-run` process owns the source tree;
3. read exactly these broad authorities:
   - `AGENTS.md`;
   - `docs/specifications/0001_GENERATIVE_CURRICULUM_FACTORY.md`;
   - `docs/architecture/10_CURRICULUM_AUTHORITY_CONVERGENCE_20261019.md`;
   - `docs/specifications/0005_FACTORY_MICROSPEC_WORKSTACK.md`;
   - `docs/tasks/0003_FACTORY_CLOSURE_WORKSTACK.json`;
4. record SHA-256 digests for those five files in the first run receipt;
5. run `python3 scripts/check_factory_workstack.py --execution-ready`;
6. stop before implementation if the workstack is invalid.

Also bind the run to the exact base commit and exact issue #150 body. Canonicalize the
bootstrap fields deterministically and record one `bootstrap_sha256`. If any bound
authority or manifest hash changes mid-run, stop the whole run and re-bootstrap
rather than continuing under mixed authority.

Do not reread the broad authorities before every leaf. Re-read them only if their
recorded digest changes or a leaf explicitly names a newer amendment.

## Reconstruct execution state

The manifest is the dependency graph. GitHub issue comments are durable execution
receipts. For every manifest leaf, use its exact mapped issue only; do not search for
replacement issues by title.

Before treating a leaf as executable, hash its local spec bytes and fetched issue body
and require exact equality with `spec_sha256` and `issue_sha256` in the manifest.

Treat a leaf as done only when its issue contains a verified `FACTORY_LEAF_DONE`
receipt naming:

- exact `spec_id`;
- exact remotely visible commit SHA;
- focused proof commands/results;
- no unresolved required work for that invariant.

Treat a leaf as blocked for the current run when its latest applicable receipt is
`BLOCKED_SPEC_GAP`. A blocked leaf is not done. Its descendants remain unready.

Pass the reconstructed IDs to `scripts/check_factory_workstack.py` with repeated
`--done SPEC-####` and `--blocked SPEC-####` arguments to compute the current ready
set.

## One-leaf execution loop

For each ready leaf:

1. read the leaf spec;
2. read only its mapped GitHub issue and predecessor completion receipts;
3. read only files and symbols in the spec's read allowlist;
4. confirm the actual named symbols still match the spec's assumptions;
5. implement only the predetermined design inside the write allowlist;
6. preserve every compatibility/wire/error contract named by the spec;
7. run the leaf's exact focused proof commands;
8. inspect the diff and `git diff --check`;
9. create one leaf-scoped commit where practical;
10. refetch before push, push normally without force, and read back the remote SHA;
11. post and read back one issue receipt;
12. recompute the ready set and continue.

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

Then recompute readiness and move to another unrelated ready leaf.

## Exploration prohibitions

During ordinary leaf execution do not:

- broadly explore the repository;
- run unrestricted `rg` across the tree;
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
