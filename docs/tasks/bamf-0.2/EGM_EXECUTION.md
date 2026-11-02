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
dependencies/current unified are consumable; affected tests and hosted checks are
green; and the exact PR head is otherwise ready for human merge review. Intermediate
fixes use focused adversarial regressions, ordinary independent review and CI. Do
not spend a fresh Goldfish after each remediation issue, individual defect fix,
merge-forward or checkpoint.

If a merge-readiness EGM finds new Blocker/Major defects, record that exact-head
review and route independently remediable work to durable issues. Repair the whole
known set before requesting another fresh EGM on the next stable merge candidate.
A same-context review is not a Goldfish review. If the pinned checkout or an
independent review is unavailable at merge readiness, record `EGM_PENDING`; do not
call the leaf fully reviewed. Older copied issue/mirror language saying "one repair
pass and one targeted re-audit" is superseded by this section. Never include
credentials, private source text or student state in the review packet. IPR-0220
remains an opaque authority reference.
### Finding and remediation lifecycle

The parent merge candidate owns the EGM result. A remediation child does not remain
open until the parent eventually passes EGM. Once the child's exact defect is
reproduced, fixed, regression-covered and verified on a durable PR/head, close the
child issue and mark its PR ready if that PR's own scope is complete. The parent
must consume the fix before its next merge-readiness EGM.

A later EGM finding reopens that child only when it demonstrates that the same
recorded defect still exists or the fix was reverted. A distinct failure mechanism
or newly exposed gap gets a new remediation issue with its own reproduction and
acceptance. This keeps the open issue/PR set aligned with actionable work rather
than accumulating historical review findings.
When the authorized parent candidate branch can take the repair without violating
writer ownership, apply the fix there and use the remediation issue as the durable
finding record. Create a stacked remediation PR only when isolation is materially
useful; do not create one solely for archival provenance.

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
