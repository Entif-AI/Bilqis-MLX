# C15.3 reconciliation checkpoint — 13 November 2026

Issue: #540 (`C15.3`). Reviewed-unified baseline: `97a018ed7e9697fe284abd9fa8197cd7f4194b45`.

## Live authority and publication

The repaired live-issue verifier now keeps native parent/child hierarchy separate from prerequisite edges and canonicalizes GitHub's optional terminal newline. After source-authorized reconciliation it reports:

- **43/43 owner issue bodies** match live GitHub;
- **172/172 recursive child bodies** match live GitHub;
- **190 native parent/child edges across 65 parent groups** match live GitHub, including the audited post-registry remediation/subleaf supplement;
- **215 dependency nodes** are valid and acyclic.

Two substantive body drifts were reconciled according to their actual source chronology. C07.1/#508 live authority was newer and added the accepted C07.1c/#955 grandchild, so the repository mirror and child-registry digest were refreshed. C11.1/#522 repository authority was newer and already embodied the later accepted C16.1a/current-unified contract, so the live issue body was updated from that exact mirror. C02.5/#905 differed only by GitHub terminal-newline transport and required no semantic rewrite.

Fifteen missing native sub-issue links were restored and read back: `349→578`, `355→577`, `357→575`, `357→594`, `359→576`, `367→635`, `371→905`, `372→904`, `418→553..557`, `471→586`, and `541→950`. A separate audited `native-hierarchy-supplement.json` now preserves later accepted remediation/subleaf hierarchy without mutating the frozen 172-child planning/dependency registry. The live verifier keeps those hierarchy edges distinct from the 215-node prerequisite DAG.

## Active native Docs

Both approved BAMF Google Docs were read at their current revisions. The SPEC continues to require C15 to reconcile live bodies, exact mirrors/workstack fingerprints, both native Docs and executable acceptance receipts, with unexecuted fixtures remaining unverified. The Blueprint continues to require a functional recursive self-maintaining Factory, grade-label permutation discriminators, actual observed behavior rather than named tests, and the `PRIVATE_REAL` public-exclusion boundary. No newer C15 contract conflict was found.

## Functional Factory proof status

The current tree contains and now has fresh current-head execution receipts for all seven #540 behaviors: pure/idempotent planning; grade-label permutation with symmetric debt and true holds; source-family/domain-rule variation; recursive replan after admission/correction; fixed-point/held termination; single-authority admission; and exact cold resume.

The repository-local venv still stops at the previously recorded missing `pyshacl` boundary, but an already-provisioned Python 3.14 environment at `/Users/cr8s/Code/Bilqis-485-venv/bin/python` was discovered with `pyshacl`, NumPy and MLX already installed. No package installation or environment mutation was performed. Running the repository's own `scripts/run_tests.py` under that interpreter produced **64/64 PASS** across the exact named witness files: planner/event/progress 17/17; semantic-family rule dispatch 5/5; v2 grade-permutation/symmetric-debt 3/3; recursive admission/replan/fixed-point 7/7; single-authority admission/epoch serialization 12/12; cold-resume/first-start custody 9/9; C03 grade/prerequisite symmetry 7/7; retention/promotion grade invariance 4/4. No live learner, live optimizer start, package install, or durable student mutation was performed.

## Remaining blockers

C13/#385 and C14/#386 remain provisional. C13 still owes the accepted integrated retained-learning/rollback/cold-resume witness. C14 still owes its accepted parent/integration receipt after C13. Those upstream gates are preserved rather than inferred from this leaf's now-executed Factory witnesses.

Protected `PRIVATE_REAL`, private journal and unclassified payloads remain outside this public artifact. Software delivery remains **IN_PROGRESS** and full-atlas student mastery remains **NOT_CLAIMED**.
