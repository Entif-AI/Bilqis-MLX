# TASK-0003: Execute the issue #150 factory micro-spec pages

**Parent:** `Entif-AI/Bilqis-MLX#150`.
**Authority:** the bookmarked leaf issue, its leaf specification, its
`FACTORY_PAGE_GATE_V1`, and only the direct prerequisite receipts named by that
page.
**Mutation posture:** bounded leaf implementation only.
**Neural authority:** this task never authorizes a real `--human-run` neural
update.

## Goal

Execute the already-groomed factory leaves sequentially while keeping each model
context bounded to one page of the work. The durable tickets and process gates
are the runner. There is no separate LLM orchestrator, local execution harness,
sidecar coordinator, or model-visible global workstack.

The workstack fixes the reusable factory. It does not create or execute one
issue per future semantic root.

## The bookmark

The only continuation state an executor needs between sessions is the current
GitHub issue number.

On start or resume:

1. verify the intended branch/worktree and current writer-coordination state;
2. verify no human-owned `bilqis_mlx.cli train --human-run` process conflicts
   with the bounded source mutation;
3. open **only the bookmarked issue**;
4. read its latest `FACTORY_PAGE_GATE_V1` comment;
5. follow that page-local gate.

Do not start by reading issue #150, `AGENTS.md`, SPEC-0001, SPEC-0005, the
authority-convergence record, the 77-leaf manifest, or every issue receipt.
The leaf spec already distills the authority needed for ordinary execution.
Read a broader authority only when the current leaf itself explicitly names it
inside its bounded read contract.

After a quota window, context reset, or process restart, reopen only the
bookmarked issue. There is no global execution state to reconstruct in model
context.

## Page-local entry gate

Every leaf issue has an additive `FACTORY_PAGE_GATE_V1` comment. Issue bodies
remain unchanged so their frozen hashes remain valid.

For the bookmarked page:

1. If this page already has a latest terminal receipt of
   `FACTORY_LEAF_DONE`, `BLOCKED_SPEC_GAP`, or
   `FACTORY_DEPENDENCY_BLOCKED`, do not rerun it. Turn directly to the
   gate's `next_page`.
2. Read only the direct prerequisite issue(s) listed in this page gate.
3. Inspect only each prerequisite's latest terminal receipt.
4. Interpret those receipts locally:
   - `FACTORY_LEAF_DONE`: prerequisite satisfied;
   - `BLOCKED_SPEC_GAP` or `FACTORY_DEPENDENCY_BLOCKED`: this page is not
     executable; post `FACTORY_DEPENDENCY_BLOCKED` here and turn the page;
   - no terminal receipt: the bookmark is inconsistent; open only the first
     missing prerequisite issue and follow its page gate.
5. If every direct prerequisite is satisfied, read this leaf spec and its exact
   read allowlist and execute the predetermined design.

The frozen lexical `SPEC-####` order was verified during grooming to be a
topological ordering. That fact is encoded in the page-turn comments. The
executor does not recompute, verify, or hydrate that global graph.

## One-page execution

For one executable page:

1. read the leaf spec;
2. read only files and symbols in its read allowlist;
3. confirm the named symbols still match the leaf's assumptions;
4. implement only the predetermined design inside the write allowlist;
5. preserve every compatibility/wire/error contract named by the leaf;
6. run the leaf's exact focused proof commands;
7. inspect the diff and run `git diff --check`;
8. create one leaf-scoped commit where practical;
9. refetch before push, push normally without force, and read back the remote
   SHA;
10. post and read back the leaf's terminal issue receipt;
11. open the `next_page` named by the current page gate.

Do not prefetch the next leaf before the current page has a terminal receipt.
After turning the page, discard prior-page model context except commit/receipt
references explicitly required as a direct prerequisite by the new page.

## Terminal receipts

A successful leaf keeps the existing `FACTORY_LEAF_DONE` shape:

```text
FACTORY_LEAF_DONE
spec_id: SPEC-####
bootstrap_sha256: <existing run binding when required by the frozen issue contract>
spec_sha256: <exact frozen spec hash>
issue_sha256: <exact frozen issue-body hash>
commit: <remote SHA>
work_completed: <bounded summary>
proof: <commands and results>
work_not_completed: none
blockers: none
unresolved_questions: none
```

If a legacy receipt field requires an already-established run binding, reuse the
valid value available from this page or its direct predecessor receipt. That
compatibility field is not permission to rehydrate the old broad bootstrap.

If this leaf's own contract is insufficient, use its existing
`BLOCKED_SPEC_GAP` receipt and turn to `next_page`.

If this leaf cannot execute because a direct prerequisite is blocked, do not
read repository code for this leaf. Post:

```text
FACTORY_DEPENDENCY_BLOCKED
spec_id: SPEC-####
blocking_prerequisites: <SPEC IDs/issues>
observed_terminal_receipts: <comment URLs/IDs>
next_page: <issue number from FACTORY_PAGE_GATE_V1>
```

Then turn the page.

## Exploration prohibitions

During ordinary page execution do not:

- read or reconstruct the full workstack manifest;
- fetch all #150 leaf issues or comments;
- compute a global ready/done/blocked set;
- read the parent #150 issue for navigation;
- broadly explore the repository;
- run unrestricted `rg` across the tree;
- search Git history for architecture archaeology;
- search all GitHub issues for alternatives;
- browse the web for a different design;
- create new abstractions not authorized by the leaf;
- invent semantic-root tickets to keep the run busy;
- start neural training.

Exact-reference checks explicitly required by the current leaf remain allowed.
If the leaf cannot proceed inside its bounded contract, emit the appropriate
terminal block receipt and turn the page.

## Questions

Do not stop the overall traversal merely because one page raises a question.
Record the question in that page's terminal receipt. If the question blocks only
that leaf, use `BLOCKED_SPEC_GAP` and continue to `next_page`. The GitHub
issue is the durable question buffer.

## Verification cadence

Run only leaf-focused verification after an ordinary leaf. Run a wave or
terminal gate only when the current ticket explicitly requires it. Do not
discover wave boundaries by hydrating the manifest.

After the final `SPEC-0082` page, its gate returns to issue #150 for terminal
closure.

Never claim neural learning, generalization, or student progress from this
workstack.
