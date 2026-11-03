# BAMF-0.2 independent EGM review

Use Google [Elephant-Goldfish Model](https://github.com/google/elephant-goldfish-model)
at commit `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. The local checkout is `../bamf02-egm-b3a359/`; it is a tool dependency, not a second source
of Bilqis policy. If it is missing, obtain and pin it before the review:

```sh
git clone https://github.com/google/elephant-goldfish-model.git ../bamf02-egm-b3a359
git -C ../bamf02-egm-b3a359 checkout --detach b3a35956759bf7f024af2ff061b2e0b44b438e4c
git -C ../bamf02-egm-b3a359 rev-parse HEAD
```

Require the exact pinned SHA. Read `../bamf02-egm-b3a359/docs/codex.md`, then the actual
personas `../bamf02-egm-b3a359/agents/codebase_details.md` and
`../bamf02-egm-b3a359/agents/comprehension.md`. Apply the appropriate standard in
`../bamf02-egm-b3a359/resources/document_standards/`, including
`implementation-readiness-standard.md` for implementation readiness. The full
checkout is required: persona and standard files are not bundled into this repo.

<!-- BAMF02:EGM-MERGE-READINESS-GATE:20261102 -->
The implementing agent is the Elephant. A Goldfish starts with fresh context and
receives only the leaf contract, its named source, diff, verification results and
necessary authority boundaries. It does not read the implementation conversation,
prior agent findings or memory.

Fresh pinned EGM is a **merge-readiness gate**, not a per-fix regression loop.
Before requesting it, clear the complete known engineering queue: every known
Blocker/Major is repaired or evidence-backed contested; independently remediable
failures have durable issues and their accepted fixes are consumed; required
dependencies/current unified are consumable; affected tests and every available
branch check are green; and the exact candidate head is otherwise ready for human
merge review. Intermediate fixes use focused adversarial regressions, ordinary
independent review and CI. Do
not spend a fresh Goldfish after each remediation issue, individual defect fix,
merge-forward or checkpoint.

Track the review state on the owning issue. Add `EGM-Pending` only when a new
whole-candidate review is actually pending. Replace it with `EGM-Passed` after a
complete PASS, or `EGM-Failed` after any Blocker/Major failure. Label each coherent
remediation issue created from that failure `EGM-Mitigation`. Keep `EGM-Failed` on
the owner during repair. Replace it with `EGM-Pending` only after the complete known
failure set is repaired and the next exact head is again ready for review. A
behavior-changing commit after `EGM-Passed` invalidates that PASS for merge
readiness.

Open the PR only after `EGM-Passed` and all pre-PR gates are green. PR-hosted checks
then provide the final integration gate. If a hosted failure requires a
behavior-changing repair, remove the stale PASS state and return to `EGM-Pending`
only when the repaired whole candidate is again ready for exact-head review.

If a merge-readiness EGM finds new Blocker/Major defects, record that exact-head
review and route independently remediable work to durable issues. Repair the whole
known set before requesting another fresh EGM on the next stable merge candidate.
A same-context review is not a Goldfish review. If the pinned checkout or an
independent review is unavailable at merge readiness, keep or add `EGM-Pending`; do
not call the leaf fully reviewed. Older copied issue/mirror language saying "one
repair pass and one targeted re-audit" is superseded by this section. Never include
credentials, private source text or student state in the review packet. IPR-0220
remains an opaque authority reference.
## Bounded convergence override

The pinned `b3a359...` checkout is retained for reproducible reviewer personas and
standards. Its historical review-loop driver repeats until zero findings or manual
halt. BAMF does **not** inherit that unbounded termination behavior.

### Review episode

- Give each whole merge-candidate review lineage one stable episode identity.
- Keep the same episode across ordinary repair commits, merge-forwarding required by
  the same candidate, and exact-head changes that only resolve findings from that
  episode.
- Increment one monotonic round number for every complete whole-candidate Goldfish
  round. Changing the SHA does not reset the counter.
- The default episode cap is five complete rounds.
- One complete clean round is sufficient for BAMF implementation merge readiness.
  A clean round has no unsettled Blocker/Major and no requested reviewer marked
  missing/failed.
- At the cap, or on churn, stop automatic review. Return the candidate to design or
  obtain explicit human authority to continue. Do not silently mint another episode.

Churn means a new blocking finding reverses or materially conflicts with a repair
made to satisfy an earlier finding at the same ownership locus, or successive rounds
keep moving the same contract boundary without converging.

### Finding triage before repair

Every Blocker/Major must state its blocking basis and locus. The blocking basis is a
violated named requirement/authority, a concrete in-scope failure, or a missing
required ownership/interface/acceptance seam. Classify the locus as
`TARGET_LOCAL`, `SHARED_CONTRACT`, `PARENT_INTEGRATION`, `AUTHORITY_GAP`, or
`MECHANICAL_PROOF`.

Repair shared/parent/authority findings at their canonical owner and pause only the
affected descendants. If two or more late findings share the same root premise or
owner, promote one systemic finding and stop reviewing descendants against a moving
foundation until that owner is repaired and rechecked.

### Proof routing

Run deterministic proof before Goldfish. Contract-mirror reconciliation,
traceability, schema/count checks, source census, dependency readiness, file/ABI
identity, and other mechanically decidable facts belong in scripts, tests, or focused
audits. A finding classified `MECHANICAL_PROOF` is closed by its deterministic
red/green proof and does not require a separate fresh EGM round. Repeated mechanical
findings should become validator coverage rather than recurring reviewer prompts.

Goldfish remains appropriate for semantic ambiguity, hidden ownership, unsafe
integration behavior, cross-boundary failure modes, and implementation-readiness
questions that deterministic proof cannot establish.

### Semantic staleness

Classify changes before invalidating review evidence:

- `NONSEMANTIC`: prose, formatting, bookkeeping, receipt/link cleanup. No fresh EGM.
- `MECHANICAL_CONFORMANCE`: machine-checkable traceability, mirror, census, or schema
  repair. Run deterministic proof; no fresh EGM solely for this change.
- `LOCAL_SEMANTIC`: meaning/behavior within one owned boundary. Re-review that scope.
- `DEPENDENCY_SEMANTIC`: consumed authority/interface/source meaning changed. Re-review
  only the impacted consumers.
- `ARCHITECTURE`: ownership/decomposition/topology changed. Return the affected scope
  to design before further implementation review.

The owning issue records episode ID, round count, latest reviewed head, open finding
IDs/loci, and disposition. This state survives compaction and agent turnover.
### Finding and remediation lifecycle

The parent merge candidate owns the EGM result. A remediation child does not remain
open until the parent eventually passes EGM. Once the child's exact defect is
reproduced, fixed, regression-covered and verified on a durable branch/head, close
the child issue. Open a remediation PR only when that branch is ready to merge. The
parent must consume the fix before its next merge-readiness EGM.

A later EGM finding reopens that child only when it demonstrates that the same
recorded defect still exists or the fix was reverted. A distinct failure mechanism
or newly exposed gap gets a new remediation issue with its own reproduction and
acceptance. This keeps the open issue/PR set aligned with actionable work rather
than accumulating historical review findings.
When the authorized parent candidate branch can take the repair without violating
writer ownership, apply the fix there and use the remediation issue as the durable
finding record. Create a stacked remediation PR only when isolation is materially
useful and the stacked branch is itself ready to merge; do not create one solely for
archival provenance or as a status marker.
BAMF integration commonly targets non-default branches, where closing keywords do
not reliably retire the linked issue. Explicitly verify and close each satisfied
remediation issue after its repair is accepted or consumed.

## Lane ownership and dependency checks

The existing long-lived branches are `codex/bamf02-a-semantics`,
`codex/bamf02-b-neural`, and `codex/bamf02-c-runtime`. Lane A owns new semantics
and Factory modules; B owns new neural modules; C owns shared trainer, CLI,
checkpoint and integration surfaces. B13 proposes checkpoint changes through
C's shared-file queue. Submit proposed changes to the Lane C owner on the
relevant B13 issue; the C writer applies them to the Lane C branch, with the
proposal and resulting commit linked in the issue receipt. The queue covers
`mlx_checkpoint.py`, `checkpoints.py`, and `boundary_commit.py`, as recorded in
the workstack. One writer per lane is an operating responsibility, not a
claim that branch existence provides a lock. Accepted sibling changes enter through
`codex/bamf-unified-base-20261028` after human review; before each leaf, fetch and
merge current unified into the assigned lane if needed, then record its SHA.
Never merge a sibling lane or `main` directly into a lane.

Run the workstack and issue-contract checks from the repository root:

```sh
python3 -B scripts/check_bamf_workstack.py docs/tasks/bamf-0.2/workstack.json
python3 -B scripts/verify_bamf_0_2_contracts.py
```

The first checks the owner workstack and its adjacent recursive child registry,
including owner declarations and an independent `issue-map.json` inventory,
missing dependencies, parent/dependency cycles, cross-lane file or directory
claims, and catalog-typed boundary errors; its output schema is
`bilqis.bamf.workstack.validation/v1`. It does not prove a writer lease, issue
completion, live GitHub consistency or a dependency receipt. The second checks
checked-in mirrors and the recursive child contracts; it explicitly does not claim
live GitHub or executable Factory proof. For each selected child, read its live
issue and each direct prerequisite's exact pushed receipt before implementation.
The #486 dependency receipt is
https://github.com/Entif-AI/Bilqis-MLX/issues/486#issuecomment-6480640011.
Review and commit/push status remain distinct from human acceptance into unified.
