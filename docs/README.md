# Bilqis documentation map

This directory is organized by **authority and purpose**, not by the date a file happened to be written.

The curriculum architecture did not originate with SPEC-0001. Earlier roadmaps, issues, registries, source records, and architectural work already required typed semantics, prerequisite-aware generated curriculum, independent source/oracle evidence, compositional reuse, and a reusable factory. SPEC-0001 consolidates those pre-existing requirements into an enforceable runtime-cutover contract. The historical failure was repeated implementation drift from that authority plus insufficient structural enforcement.

## Current authority

- [`specifications/`](specifications/) contains numbered normative repository specifications. Start with [`0001_GENERATIVE_CURRICULUM_FACTORY.md`](specifications/0001_GENERATIVE_CURRICULUM_FACTORY.md). [`0004_TYPED_ERROR_CONTROL_PLANE.md`](specifications/0004_TYPED_ERROR_CONTROL_PLANE.md) governs operator-visible failures, recovery and the error-debt migration. The hard runtime rule is **no factory release, no grade**.
- [`tasks/`](tasks/) contains numbered execution packets. [`0001_IMPLEMENT_GENERATIVE_CURRICULUM_FACTORY.md`](tasks/0001_IMPLEMENT_GENERATIVE_CURRICULUM_FACTORY.md) is the implementation/verification contract for SPEC-0001.
- [`architecture/`](architecture/) contains current architectural explanations that remain compatible with the numbered specifications. Architecture documents do not outrank a numbered spec or external governing authority.
- [`operations/`](operations/) contains current operator/repository procedures. Start with the [`Bilqis Operator Field Manual`](operations/OPERATOR_FIELD_MANUAL.md) for hard-stop diagnosis and recovery. Operational instructions do not redefine curriculum semantics.

## Evidence and provenance

- [`evidence/`](evidence/) contains observations, experiment receipts, diagnostics, grade evidence, and development qualification artifacts. Evidence can prove or falsify a claim; it does not become policy merely by existing.
- [`provenance/`](provenance/) contains source manifests, registry snapshots, adjudication records, review dossiers, source audits, and derivative requirement companions. These artifacts preserve what an implementation was grounded in. They are not duplicate canonical specifications.

## History

- [`history/`](history/) contains superseded proposals, archived migration sketches, old work packets, and pre-canonical documentation retained for forensic and historical use.
- Material in `history/` may explain why the current system looks the way it does, but it must not be used to reopen a settled current contract without newer authority.

## Repository rules

Only this `README.md` belongs at the `docs/` root. New normative specifications go in `specifications/`; execution prompts go in `tasks/`; current architecture, operations, evidence, provenance, and superseded material go in their corresponding directories.

Move documents with `git mv` so history remains inspectable. Do not create compatibility copies after a move. Repair callers and links instead. Do not delete forensic evidence simply to make the tree prettier.

Unit and contract tests belong beside the package that owns their invariant. The top-level `tests/` directory is reserved for genuine integration, system, compatibility, and disposable end-to-end proofs.
