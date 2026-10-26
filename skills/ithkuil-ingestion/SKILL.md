---
name: ithkuil-ingestion
description: "Rebuild pinned New Ithkuil source tables and inspect extraction debt in Bilqis-MLX using deterministic repository commands. Use for source-to-CSV rebuilds, not curriculum admission or neural training."
---

# Ithkuil Ingestion

This implementation exposes Stage A only. Semantic build, conformance and optional
graph orchestration are governed by the contract but not yet exposed by this Skill.

## Authority preflight

Resolve the explicit repository/worktree and Python interpreter. Read current
`AGENTS.md`, `lib/ithkuil/ingestion_contract.json` and applicable source profiles.
Use [references/authority.md](references/authority.md) for project governance,
publication posture or authority conflicts. Public-only access does not authorize
protected operations; stop and route unresolved protected requirements to their
owner. Surface conflicts rather than silently reconciling them.

## Rebuild pinned sources

Read [references/source.md](references/source.md), then invoke the repository's
`lib.ithkuil.src.ingestion` source action with explicit repository, interpreter and
source selection. It stages the existing canonical owners; do not copy parser
rules into a prompt or generate missing source rows. Default execution is offline.
Do not call the snapshot fetcher's main routine to fix a hash mismatch.

Return the normalized result, source-manifest identity, artifact references,
frontier receipt and explicit debt. A non-success result stops downstream work.
Read-only debt inspection reads existing receipts; do not invoke a publishing CLI
under an inspection request.

## Postflight and recovery

Validate the actual result and referenced artifact digests after action. Preserve
partial/held/debt status; source availability is not semantic or curriculum
admission. Use the run's typed failure and evidence for retry/reconciliation.
Never blindly replay an ambiguously acknowledged publication.

No curriculum/training/checkpoint/optimizer mutation, pin override, graph reset,
default graph fallback, Git push/merge or external publication is authorized by
this Skill. Graph operations are not part of this Stage-A implementation.
