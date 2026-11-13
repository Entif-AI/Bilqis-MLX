# C07.2 explicit disposable lease renewal

PARTIAL_PENDING_PLANNER_AND_UPSTREAM. IPR-0220; base2f8e79ef7bcb15b81488837189740ba371b28546, consumed unified da0431bee37c0e4f766f05cc94ceb6b23ac7d054.

Initial issuance and explicit renewal share a stable exclusive file lock. Renewal verifies current replacement authority, same independently supplied run identity, exact prior digest, distinct request/lease identities and strictly later timestamp. Immutable replacement and renewal-edge receipts precede atomic current-pointer publication. Exact replay verifies its predecessor edge. Old lease artifacts remain. Restricted historical approval need not be currently admissible, but immutable prior identity/digest must match. Narrower renewed scope is legal. Saved learner custody remains forbidden for these fixture authorities; CLI/native admission remains unavailable.

13 lease/renewal tests pass, including interruption/replay, stale requests, competing renewals with exactly one winner, wrong lineage, changed signature, restricted prior authority, narrower scope and saved-run refusal. Fresh independent pinned EGM review found no scoped Blocker/Major and independently ran12 tests before two minor follow-ups (import placement and extra direct witnesses). Those follow-ups are included. No actual learner/AdamW, source promotion, graph or generation actions.

Human-started boolean/command digest/time remain caller assertions, not authenticated human authority. Full511 needs native B13 custody, continuation and actual predecessor/adoption/planner integration; this slice cannot close511. PR550 stays draft/unmerged. Historical debt scope/policy remains NOT_MEASURED in the separate native debt view.
