# C11.1 current preflight independent review — 1 November 2026

Independent reviewer `/root/c678_review_fresh` began with no conversation history
and reviewed source `006a4c55967807dd0428533842ab7fc3665f54d1`, its implementation
delta from `ac4bbc87`, the plan, tests and direct authority owners. The reviewer
verified EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c` and read `docs/codex.md`,
`agents/codebase_details.md` and `agents/comprehension.md`. Review was strictly
read-only; tests and hosted checks were not independently rerun.

No Blocker or Major finding. Narrow held read-only inspection is acceptable:
actual v2 topology reaches held JSON before learner dispatch, manifest bytes are
opaque/NOT_VERIFIED, C07 scopes are refused, legacy state is not coerced and BAMF
pointers are not loaded. Non-dry-run v2 keeps the runtime refusal.

Two nits are addressed in focused tests: the cold subprocess now inspects amid a
populated temporary tree and compares all file bytes and file/directory mtimes,
including the root; direct refusal assertions cover lease scopes, missing resume
pointers, directory/missing Atlas manifests and manifests on legacy/live dispatch.
The no-MLX import blocker remains active in the cold process. No production
preflight code changed for these repairs.

This supersedes the prior reviewer-credit EGM_PENDING observation for the reviewed
bounded increment. Full #522 remains open: production create/resume, persisted
policy and conflicting override proof and accepted A12/B13/C05/C07 integration
remain required. No durable learner operation, source qualification or self-merge.
