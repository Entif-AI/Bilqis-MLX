# C06.3 — source-qualified discrepancy aggregation

Status: **IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION**; issue #506 remains open.
Lane codex/bamf02-c-runtime; prior implementation7020cd52f62ff75d15cfd37f50bd172359711237.
Consumed unified7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4, unchanged on fresh fetch.
IPR-0220. No persistent learner, own AdamW, graph or accepted-generation writes.

`aggregate_salience_patterns` consumes C06.2 signed history and fixed20-event
completed windows. Window clusters retain every analogous observed minor defect,
including clusters below the C06.2 per-window nomination threshold. A separate
signed/versioned AggregationPolicy explicitly counts the union of independent
lineage roots across completed windows. Its pattern minimum, contributing-window
minimum and minimum new roots per contributing window are explicit. A repeated
root remains an observation without adding independent support. Unrelated
structures/defects and different capability/source/rights/correction partitions
remain separate. Stable pattern identity does not change when its evidence grows;
its evidence digest does. Trend points retain each window's new/cumulative roots.

Signed annotations reference exact retained event digests, conjecture digests and
alternative-explanation digests. Unknown references, invalid signatures and
divergent annotation IDs fail through the ErrorBus. Exact annotation replay is
idempotent. Missing annotations are explicitly listed. Patterns retain constituent
window/event identities, all source contexts, full observations, lineage unions,
observation time bounds and producing rule. Every candidate remains CONJECTURE,
source_gold=False, qualified_for_teaching=False. The output exposes grouped
investigation IDs, never a teacher option or optimizer row.

Historical evidence is revalidated under its historical authority before any
aggregation. Current rights/context/source-signer key/scope changes yield an
explicit CURRENT_SOURCE_OR_RIGHTS_HELD while retaining historical pattern data
and suppressing investigation nomination. Historical corruption is a typed error,
not an ordinary hold. Current annotation and aggregation-policy signatures must
remain authorized. This adapter does not qualify a conjecture or bypass ordinary
source admission, consent, missing gold or held-source owners.

Schemas: bilqis.c06.aggregation-policy/v1, observation-annotation/v1,
candidate-pattern/v1 and salience-aggregation/v1. Rule:
COMPLETED_WINDOW_UNION_UNIQUE_LINEAGES/v1.

Proof: **79 affected owner tests passed, zero failures/errors/skips** in tests.txt.
The five new tests cover independent20 vs paraphrases/unrelated defects, two
subthreshold windows accumulating four roots, repeated windows adding zero roots,
stable pattern vs changing evidence digest, retained rights/key-scope holds,
conjecture/alternative provenance and malformed signatures/references/IDs.
Independent Goldfish /root/c06_1_goldfish completed cold review and implementation
review using Google EGM pin b3a35956759bf7f024af2ff061b2e0b44b438e4c.
Disposition PASS, no blocker/major. Reviewer inspected five-test green receipt;
reviewer did not execute tests. Cold-review threshold and HOLD distinctions were
resolved in the initial implementation. No new implementation incident identified.

Upstream assumptions: C06.2 signed event/current-source interfaces are provisional
fixtures for A09/B13; source lineage roots and admitted rights epochs must later
come from their accepted owners. Actual A06/C09 typed contracts are reused. No
replacement upstream source/custody/backend implementation was added. Actual
accepted A09/B11/B13 and disposable MLX/integration requalification remain pending.
PR #550 stays draft/unmerged. Continue C06.4 #507.
