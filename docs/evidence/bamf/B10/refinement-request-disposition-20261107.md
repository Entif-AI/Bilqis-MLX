# B10 refinement request disposition checkpoint — 2026-11-07

## Scope

This checkpoint closes the missing source-derived request-disposition seam needed
before B11 may compose B06.2 into B06.3. The prior B06 API accepted two raw
caller booleans, `explicit_member_question` and `unresolved_nested_query`, but no
production owner derived those semantics from the source-owned task contract.

This patch does not modify B06 policy or compose B11. Accepted B10 children remain
closed; this is a scoped B10-parent integration repair.

## Exact identity

- reviewed unified base: `bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`
- branch: `codex/367-b10-refinement-disposition-20261107`
- semantic head: `d63bd8f9f4699087d67a6f4c740a9120a58ddf2a`

## Contract

`bilqis_mlx/runtime/_capability/refinement_request.py` defines a closed,
immutable disposition derived only from a validated C04 `TaskGoal`:

- `ORDINARY`
- `EXPLICIT_MEMBER`
- `UNRESOLVED_NESTED`

The derivation is structural:

- an unresolved task node consuming an earlier `RESULT` is nested-unresolved;
- otherwise direct typed frame-member `INPUT` operands are explicit-member and
  supply their source-owned requested roles;
- flat source-literal tasks are ordinary.

No caller may supply the classification boolean or credential.

## Proof

Exact-head snapshot-pinned `m3-ultra` run at `d63bd8f9...`:

- 7/7 PASS in 0.888s
- real flat answer-choice source -> `ORDINARY`
- real `ADD(MUL(2,3),4)` C04 source goal -> `UNRESOLVED_NESTED`
- typed frame-member input -> `EXPLICIT_MEMBER` with role `theme`
- existing B10 TaskGoal route/proposal tests remain green

Repository checks:

- BAMF flow-control: PASS
- BAMF contract verifier: 43/43 mirrors; 214 owner/child identities/fingerprints
- `quality:changed`: PASS; zero changed-file findings; legacy trainer 6/6;
  flow-control 15/15
- `git diff --check`: clean

The workstation's default Python lacked `rdflib` and `mlx`; local attempted tests
stopped during imports before product behavior. The qualified M3 run above is the
execution evidence.

## Remaining authority boundary

This branch is not a complete B10-parent closeout and spends no fresh EGM or PR.
B11/#471 must consume this disposition only after reviewed integration and must
not reintroduce caller booleans. The remaining independent B06 production gap is
durable operator `run_seed` plus true source/visit identity; the C05 AST and
A05/A13 prefix-authority seams are separately implemented on their own branches.
