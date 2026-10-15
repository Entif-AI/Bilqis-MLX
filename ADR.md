# Architecture Decision Record

Append-only decisions from the user. New decisions get a dated entry; do not rewrite historical decisions into new authority. This log is private to the Bilqis MLX implementation.

## ADR-001 | 2026-10-15 | Private MLX successor

The user established `Entif-AI/bilqis-mlx` as the private implementation home. Controlling full text is the protected `IPR-0220` archive. Public Bilqis #160/#162 carry only publication-safe summaries. Preserve the complete old FP32 model and native AdamW, historical checkpoint archives, and prior code. Do not launch neural training as an agent.

## ADR-002 | 2026-10-15 | Genuine letter grades, not old G labels

Historical `G##` units are capabilities, not future school grades. Introduce actual lettered grades containing around six to nine comparably difficult, prerequisite-compatible capabilities, starting at A unless `--resume` was explicitly selected. Grade mastery requires one intact complete student and its own optimizer passing 100% of that grade's capabilities at one checkpoint. After each full grade pass, conduct two freshly ranked weakest-three recovery rounds from current and previously passed capabilities. Old-grade regressions need not block the current grade. A frozen champion earns one future teacher vote per mastered grade pointer, regardless of shared checkpoint file count; whole-school soup weights reflect the same pointer multiplicity, and soup is a teacher rather than a synthetic student. The old 1150/1150 rule is historical, not the new graduation criterion.

## ADR-003 | 2026-10-15 | Operator dry-runs and durable root docs

The user expressly authorizes agents to execute inert preflights and dry-runs directly. Keep concise current `AGENTS.md`, polished human-oriented `README.md`, this brief append-only `ADR.md`, and a short latest-state `HANDOFF.md`. The files may have multiple authors: coordinate with current contents and use minimal, checked edits rather than wholesale replacements.

## ADR-004 | 2026-10-15 | New Ithkuil alignment without legacy ABI rupture

Begin aligning newly introduced semantic primitives and concepts to **New Ithkuil** immediately. Preserve historical legacy semantic primitives *exactly as they are* to retain the previously trained model. New alignments are separate versioned mappings; a cognate, approximate analogy, or research seed never grants permission to relabel the original token graph, declare a new mastery gate satisfied, or test untaught abstractions. The uploaded curriculum registry is input and provenance, not automatic training authorization.
