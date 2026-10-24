# SPEC-0005: Factory micro-spec workstack and sequential executor contract

**Status:** Normative execution-architecture contract for issue #150.
**Change posture:** CONFORMANCE + MAINTENANCE.
**Parent:** `Entif-AI/Bilqis-MLX#150`.
**Scope:** Decomposition, dependency indexing, executor reading boundaries, issue/spec mapping, blocked-leaf handling, and verification cadence for the factory-closure corpus.

## 1. Purpose

Issue #150 is an epic for finishing the reusable curriculum factory described by
SPEC-0001. It is not itself an implementation unit, and its decomposition is not a
semantic-root inventory.

The workstack exists so an execution agent can spend its context and quota applying
already-decided architecture instead of repeatedly rediscovering the repository,
reconstructing dependencies, or redesigning each change in isolation.

A leaf specification is warranted only when it establishes one reusable factory
invariant or ownership boundary with one bounded proof. Future semantic roots,
capabilities, lexical items, and grade candidates are inputs to the factory and do
not receive one leaf each merely because they may be taught later.

## 2. Authority bootstrap

An executor bootstraps broad authority once per run, before choosing any leaf:

1. `AGENTS.md`;
2. `docs/specifications/0001_GENERATIVE_CURRICULUM_FACTORY.md`;
3. `docs/architecture/10_CURRICULUM_AUTHORITY_CONVERGENCE_20261019.md`;
4. this specification;
5. `docs/tasks/0003_FACTORY_CLOSURE_WORKSTACK.json`.

The executor records the SHA-256 digest of each bootstrapped file in its run receipt.
It does not reread and reinterpret those broad documents before every leaf unless a
hash changes or a leaf explicitly identifies a relevant amendment.

## 3. Leaf contract

Every executable leaf specification MUST contain:

- stable `SPEC-####` identity and parent issue #150;
- track and explicit dependency spec IDs;
- exactly one primary architectural invariant or ownership boundary;
- the current defect/root cause being removed;
- a predetermined design decision;
- distilled authority clauses relevant to the leaf;
- exact read allowlist;
- exact write allowlist;
- exact named symbols/functions/classes expected to change;
- behavior and wire contracts that MUST remain unchanged;
- internal helper/library mechanisms to reuse and explicit non-inventions;
- bounded external prior-art conclusion where applicable;
- tests owned by the leaf and exact commands to run;
- verification tier and wave;
- migration/backward-compatibility requirements;
- stop conditions and `BLOCKED_SPEC_GAP` rules;
- forbidden exploration.

If two proposed leaves require the same code mutation to make their invariants true,
they SHOULD be merged. If one leaf cannot begin without understanding another
leaf's implementation, that dependency MUST be encoded in the workstack DAG.

## 4. Workstack manifest

`docs/tasks/0003_FACTORY_CLOSURE_WORKSTACK.json` is the single machine-readable
dependency index. It is planning/execution state, not a second desired-state spec.

Each leaf entry contains only indexing data:

- `spec_id`;
- `path`;
- `spec_sha256` over the exact UTF-8 leaf-spec bytes;
- `title`;
- `track`;
- `depends_on`;
- `wave`;
- `verification_tier`;
- `issue_number` once the matching execution issue exists;
- `issue_sha256` over the exact issue body used as the execution surface.

The manifest MUST NOT duplicate read/write allowlists, design rationale, or proof
details from the leaf spec. Readiness is graph state, not issue prose.
The two hashes bind the index to the exact desired-state and execution contracts;
an execution-ready run fails closed when either bound artifact has drifted.

`scripts/check_factory_workstack.py` validates the manifest with Python stdlib
`graphlib.TopologicalSorter`. No third-party DAG dependency is permitted for this
control plane.

The validator MUST reject:

- duplicate spec IDs;
- duplicate spec paths;
- duplicate non-null issue numbers;
- missing dependency IDs;
- self-dependencies;
- dependency cycles;
- invalid spec/path numbering;
- invalid or stale spec hashes;
- missing leaf spec files;
- manifest/spec identity mismatch;
- absent issue numbers or issue hashes when execution-ready validation is requested.

The runtime/bootstrap layer additionally fetches each mapped GitHub issue and compares
its exact body hash with `issue_sha256`; the local structural validator cannot prove
remote issue bytes by itself.

## 5. Ready, done, and blocked

The manifest defines the immutable dependency graph. Dynamic execution disposition
belongs to GitHub issue state/comments and the runner's current receipt.

A leaf is **ready** only when:

- it is not already done;
- it is not blocked for the current run;
- every dependency is done;
- its issue mapping exists for an execution-ready run.

A blocked dependency never makes a descendant ready. Blocking one branch MUST NOT
prevent unrelated ready leaves from executing.
Within one ready frontier, dispatch order is lexical `SPEC-####` order so manifest
insertion order cannot change the run.

## 6. Sequential executor loop

For each ready leaf, the executor:

1. reads only the leaf spec, its GitHub issue, dependency completion receipts, and
   the leaf's exact read allowlist;
2. performs only the predetermined mutation inside the write allowlist;
3. runs the leaf's focused verification;
4. creates one verified commit for the leaf where practical;
5. posts an issue comment containing work completed, proof/tests, work not completed,
   blockers, unresolved questions, and exact commit SHA;
6. marks the leaf done in runner state only after the proof and commit exist;
7. recomputes the ready set and continues.

The executor MUST NOT use broad repository exploration, unrestricted `rg`, broad Git
history archaeology, broad GitHub search, or open-ended web research during ordinary
leaf execution. If a required fact is absent from the spec/allowlist, that is a spec
gap rather than permission to rediscover the architecture.

## 7. Blocked-spec-gap receipt

When a leaf cannot be executed under its stated contract, post a structured receipt:

```text
BLOCKED_SPEC_GAP
spec_id: SPEC-####
failed_assumption: <exact assumption that failed>
observed_fact: <bounded observed contradiction>
required_decision: <exact missing architecture decision, if any>
required_read_authority: <minimal additional path/symbol, if any>
required_write_authority: <minimal additional path/symbol, if any>
proof_attempted: <commands/evidence already run>
```

The executor then continues with another ready leaf. It MUST NOT mark descendants of
the blocked leaf ready and MUST NOT spend an open-ended run investigating the gap.

## 8. Verification cadence

Verification has three tiers:

- **Tier 0 / leaf:** exact focused tests and static checks owned by the leaf;
- **Wave gate:** package-level conformance, architecture guards, and the relevant
  cross-leaf system proof after a coherent dependency wave;
- **Terminal:** full repository suite, docs checks, factory closure/architecture
  checks, direct-v2 Grade Z proof, deterministic multi-successor runway proof, and
  all other SPEC-0001 terminal acceptance checks.

The full repository suite is not required after every micro-patch unless a leaf
explicitly declares it.

## 9. Reuse and prior art

The executor reuses repository mechanisms first. For this workstack:

- use stdlib `TopologicalSorter` for dependency ordering and cycle detection;
- reuse `SourceAdapterRegistry` rather than introducing a plugin framework;
- borrow import-layer/independence contract concepts where useful without adding
  Import Linter as a #150 dependency;
- deterministic zero-install proofs are mandatory; Hypothesis may be added later as
  an optional stress harness but is not #150 acceptance authority.

## 10. Acceptance

This execution architecture is conforming when:

1. the workstack manifest validates structurally and is acyclic;
2. every executable entry maps to one existing leaf spec and one GitHub issue;
3. ready-set computation is deterministic from dependency completion state;
4. blocked descendants remain blocked while unrelated leaves continue;
5. leaf specs are factory-mechanism units, not semantic-root inventory;
6. Codex can execute a ready leaf without broad architectural research;
7. issue comments provide a durable per-leaf execution/proof receipt;
8. wave and terminal gates remain explicit rather than being rerun after every leaf.
