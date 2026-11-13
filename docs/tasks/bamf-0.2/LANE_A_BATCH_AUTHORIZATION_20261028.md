# Lane A batch execution authorization

Date: 2026-10-28. Scope: the owner-authorized Lane A implementation run under #342.

The owner approved continuing successive dependency-ready leaves on
`codex/bamf02-a-semantics` while integration review is pending, then instructed
the executor to commence. This is a scoped amendment to ADR-119's per-issue
return path, not a change to any implementation requirement.

## Execution contract

Each implementing issue still starts by fetching and consuming the current
`origin/codex/bamf-unified-base-20261028`. Record the consumed unified SHA. If
already contained, do not manufacture a no-op merge. Never merge `main` or a
sibling lane directly.

Complete and verify each leaf independently. Preserve its full behavior,
acceptance, focused tests, exact commit, source evidence, EGM disposition and
GitHub issue receipt. Same-lane dependency work may consume an already committed
and verified predecessor without waiting for that predecessor's merge into
unified. Such work remains pending human integration approval, not accepted
cross-lane authority. A failed or unverified predecessor does not satisfy a gate.

Maintain one cumulative pull request from `codex/bamf02-a-semantics` into
`codex/bamf-unified-base-20261028` for this execution batch. Add implemented leaf
references and proof as each unit is completed. Keep one writer on the lane.
Independent EGM review may cover at most three cohesive leaves per review, as
already allowed by the lane's execution contract.

Human approval remains mandatory before the PR merges. The executor must not
self-merge, force-push, close integration parents prematurely, alter other lane
ownership, launch live training, or change existing student or optimizer state.

## Durable authority

The corresponding dated owner-authorization comment on GitHub issue #342 is
the public execution amendment for this run. Existing issue specifications and
their hashes remain intact. This document and `EXECUTION_LANE_A.md` make the
accepted batch behavior available after context replacement.
