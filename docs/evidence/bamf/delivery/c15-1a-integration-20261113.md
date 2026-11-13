# C15.1a integration checkpoint — 13 November 2026

Issue: #537 (`C15.1a`)

## Integration identity

- Lane: C, serialized writer `codex/bamf02-c-runtime`.
- Consumed reviewed-unified SHA:
  `97a018ed7e9697fe284abd9fa8197cd7f4194b45`.
- Lane branch was fast-forwarded to that exact SHA, pushed non-force, and read back
  remotely before C15-owned edits.
- Baseline workstack: 172 children, 43 live owner mirrors, `held_keys=[]`,
  dependency state `resolved`, executable order 215.
- No sibling lane or `main` commit was merged directly.

## Direct dependency receipts

These are integration receipts, not new ownership claims.

| Component | Issue | Disposition | Exact usable receipt | Public evidence |
| --- | ---: | --- | --- | --- |
| B14 | #375 | ACCEPTED | reviewed candidate `dd63880fdfde9d01eccbbff876e39828dbded3f6`, merge `5166aca71f01f09cfb4e533d61dc41e53a987726` | issue comment `6800933565` |
| C11 | #384 | ACCEPTED | reviewed-unified parent closeout `0ae919779e1de44f5c7c96e911b3f61780099e21`; C11.3 repair head `ce09a0c1887069385b903ac10a4d576d22d04881` | issue comment `6840426430` |
| C12 | #381 | ACCEPTED | parent closeout `516725b6170f258ad86b0c5d4ca050907238e59d` | issue comment `6754534350` |
| C13 | #385 | PROVISIONAL | latest C13.1 branch receipt `1150f7d8ca65b564906150c266c3b261ccb3b030` | #528 comment `6837301659`; its missing source/TaskGoal authority subsequently landed through #1020 / PR #1024, but the C13 disposable candidate has not yet been rerun and accepted |
| C14 | #386 | PROVISIONAL | C14.1a review-clean branch receipt `77006d2370a16e0bfb4ca1a10cc516a6e4d011f8` | #532 comment `6856445395`; C14 correctly remains open while C13 finishes |
| C16 | #382 | ACCEPTED | parent integration closeout `c672c62113108695a2a60cd0eb0d7f19d085f838` | issue comment `6832648874` |

The four accepted integration commits above are ancestors of the consumed
reviewed-unified head. C13 and C14 remain deliberately provisional. Their OPEN
state does not prevent C15 implementation against a frozen interface, but final C15
turn-in must consume their actual accepted receipts rather than promoting these
checkpoints by inference.

## C15 delivery boundary introduced here

`bilqis_mlx.runtime.delivery` adds immutable typed receipts and the required owner
API:

`BamfDeliveryManifest(components, issues, commits, proofs, egm, operator_commands)`

The manifest is canonical-JSON content addressed. Receipt collections are tuples,
sorted and unique. Every component/issue/commit carries an exact SHA or evidence
identity. Proof receipts bind input/output schema versions. The integration rule
requires these six dependency components: B14, C11, C12, C13, C14 and C16;
additional immutable component pins are permitted but cannot replace them. It also requires exactly the independent
`codebase-details` and `implementation-readiness` EGM slots, and exactly the four
operator command roles below. Provisional upstream or pending EGM evidence keeps
software delivery `IN_PROGRESS`; it can never become an implicit PASS. Student
mastery remains separately `NOT_CLAIMED`.

Boundary failures use `SCHOOL.BAMF_DELIVERY.INVALID` through ErrorBus rather than
inventing local exception strings.

## Parser-tested command reconciliation

The accepted C11/C16 runbooks expose these exact command roles:

- preflight: `npm run train -- --dry-run ...` with explicit topology, Atlas
  manifest, run identity and optimizer inputs;
- owner start: `npm run train -- --human-run --resume --run-dir
  /absolute/path/to/bamf-run --minutes 90 --reserve-gib 100 --max-visits 1`;
- cold resume: `npm run train -- --human-run --resume --run-dir
  <accepted-bamf-run>` after interruption;
- read-only status: `npm run dashboard -- --run-dir /absolute/path/to/run --once
  --atlas-details`.

The accepted C11.3 closeout receipt records 104/104 bounded selections on its exact
tree, including parser/resume, create/enrollment, preflight/lifecycle wire and
dashboard rings, with fresh independent review at zero Blocker/Major/Minor.

A fresh local rerun was attempted from this MBP worktree. It is **not** recorded as
PASS: the repository venv lacks `pyshacl` and `mlx`, so the selected CLI suites stop
at dependency import before the relevant cases execute. This environment failure
does not replace or weaken the accepted C11/C16 receipts. C15 records the failed
fresh attempt as environment evidence and does not fabricate a new command PASS.

## Verification for this checkpoint

- new delivery contract + integration + error-catalog ring: **9/9 PASS**;
- changed-module structure: PASS, zero violations;
- governance integrity: PASS, zero violations;
- changed-file smell audit: zero new findings;
- `git diff --check`: PASS.

## EGM and finish boundary

Fresh pinned Google EGM review at
`b3a35956759bf7f024af2ff061b2e0b44b438e4c` remains **EGM_PENDING**. Per the
approved packet it will review the cohesive C15.1a/C15.1b/C15.2 batch, at most three
leaves, without chat history. Blockers/Majors must be repaired or evidenced before
the batch turn-in.

This checkpoint therefore provides an exact usable C15.1a development receipt for
C15.1b, but does **not** claim #537 final completion yet. Final #537 turn-in still
requires the fresh EGM disposition and actual accepted C13/C14 receipts. No live
learner, optimizer, source-rights mutation or self-merge occurred.
