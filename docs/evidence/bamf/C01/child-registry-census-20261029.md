# C01 live child registry completeness census | 2026-10-29

The existing `check_bamf_workstack.py` local and `--live` checks validate the **registered** 157 children; they do not enumerate later GitHub child issues. A new read-only audit (`scripts/bamf/audit_child_registry.py`) compares the live GitHub BAMF-0.2 issue census against registered child issue numbers and keys. It never creates, edits, closes or merges anything. The default mode reports drift without blocking CI; `--strict` can be used at an explicit completion gate.

The first live run found **171 matching child issue records**, 157 registered entries, **14 unregistered issue records representing 13 unique keys**, and two key collisions:

- A08.1b.1 #553; A08.1b.2 #554; A08.1b.3 #555; A08.1b.4 #556; A08.1b.5 #557.
- C08.4 #558; C14.3 #559; A05.4 #575; B02.4 #576; B05.4 #577; A03.4 #578; B11.1a #586 and its closed duplicate #587; A05.5 #594.
- **B11.1a**: #586 is the canonical OPEN implementation issue; #587 is a CLOSED duplicate with explicit supersession. Do not register #587 as a second work item.
- **C14.3**: #535 is already registered and OPEN for recursive grade-neutral domain rules; #559 is a distinct OPEN asynchronous swarm-contribution feature incorrectly using the same key. The issue key must be disambiguated before registry admission, without deleting either requirement.

The audit found no registered key absent from the live search and no wrong-number mapping for an existing key. It also found a separate additive live-parent drift for B11.1 #471 (new #586 prerequisite link), not yet reconciled in this audit-only change.

Four focused literal tests pass: missing-vs-duplicate classification, complete case, wrong-number detection, and non-BAMF exclusion. The audit does not pretend the registry is complete, does not guess ambiguous prerequisites, and does not close C01.
