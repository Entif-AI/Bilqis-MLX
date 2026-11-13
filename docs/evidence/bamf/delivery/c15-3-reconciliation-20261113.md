# C15.3 reconciliation checkpoint — 13 November 2026

Issue: #540 (`C15.3`). Reviewed-unified baseline: `97a018ed7e9697fe284abd9fa8197cd7f4194b45`.

## Live authority and publication

The repaired live-issue verifier now keeps native parent/child hierarchy separate from prerequisite edges and canonicalizes GitHub's optional terminal newline. After source-authorized reconciliation it reports:

- **43/43 owner issue bodies** match live GitHub;
- **172/172 recursive child bodies** match live GitHub;
- **53 native parent/child groups** match live GitHub;
- **215 dependency nodes** are valid and acyclic.

Two substantive body drifts were reconciled according to their actual source chronology. C07.1/#508 live authority was newer and added the accepted C07.1c/#955 grandchild, so the repository mirror and child-registry digest were refreshed. C11.1/#522 repository authority was newer and already embodied the later accepted C16.1a/current-unified contract, so the live issue body was updated from that exact mirror. C02.5/#905 differed only by GitHub terminal-newline transport and required no semantic rewrite.

Fifteen missing native sub-issue links were restored and read back: `349→578`, `355→577`, `357→575`, `357→594`, `359→576`, `367→635`, `371→905`, `372→904`, `418→553..557`, `471→586`, and `541→950`.

## Active native Docs

Both approved BAMF Google Docs were read at their current revisions. The SPEC continues to require C15 to reconcile live bodies, exact mirrors/workstack fingerprints, both native Docs and executable acceptance receipts, with unexecuted fixtures remaining unverified. The Blueprint continues to require a functional recursive self-maintaining Factory, grade-label permutation discriminators, actual observed behavior rather than named tests, and the `PRIVATE_REAL` public-exclusion boundary. No newer C15 contract conflict was found.

## Functional Factory proof status

The current tree contains literal witnesses for all seven #540 behaviors: pure/idempotent planning; grade-label permutation with symmetric debt and true holds; source-family/domain-rule variation; recursive replan after admission/correction; fixed-point/held termination; single-authority admission; and exact cold resume. They are **not promoted to EXECUTED_PASS** in this checkpoint.

Fresh execution was attempted in the available environments. The repository venv reaches Python 3.14 and RDFLib but collection stops on missing `pyshacl`, `numpy`, and `mlx`. The system Python has MLX and NumPy but is Python 3.9 and fails before tests because the current repository requires modern union-type syntax. These are environment/collection blocks, not observed behavioral failures. No package installation, learner run, optimizer run or durable student mutation was performed merely to manufacture a green receipt.

## Remaining blockers

C13/#385 and C14/#386 remain provisional. C13 still owes the accepted integrated retained-learning/rollback/cold-resume witness. C14 still owes the accepted shared-scheduler multi-family program, grade permutation, three plan/admit/replan cycles, staged restart, true cross-domain hold and all-held fixed-point receipt. Those upstream gates are preserved rather than inferred from code presence.

Protected `PRIVATE_REAL`, private journal and unclassified payloads remain outside this public artifact. Software delivery remains **IN_PROGRESS** and full-atlas student mastery remains **NOT_CLAIMED**.
