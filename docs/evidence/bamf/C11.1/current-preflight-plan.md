# C11.1 / #522 current Lane C preflight step

Baseline: Lane C/unified70e37ae2. This issue branch reuses the same-Lane-C #632
checkpoint c63b07ab; the original branch/worktree remains untouched. All original
structural splits and public compatibility seams stay intact. Existing generated
error documentation is regenerated from the combined source, never waived.

The current CLI already deserializes the real B01 v2 topology but rejects it before
any dry-run report; it also lacks the prescribed --atlas-release-manifest argument.
Add a read-only configuration preflight for v2 plus that exact flag. Preserve the
existing human-run, retention and source-prefetch controls and all v1 behavior.

Create presentation/operator_cli/bamf_preflight.py with `bamf_preflight(args,topology)`.
It consumes the actual ModelTopologySpecV2 already validated by topology_from_file.
It returns a NEW C11 presentation record (schema bilqis.bamf.operator-preflight/v1),
result HELD_PENDING_SOURCE_AND_GENERATION_AUTHORITY, actual topology/architecture
and digest, requested run/resume/policy, optional manifest path/raw-file SHA-256,
requested prefetch worker count, requested retention/human-run settings, and zero
neural updates. Manifest qualification is explicitly NOT_VERIFIED; A12 alone owns
its schema and meaning. Stream its hash without parsing or publishing its contents.
No synthetic or guessed A12 release format is introduced.

Atlas-release policy requires a manifest reference; staged policy with a manifest
rejects. Missing/symlink/non-file manifest paths reject through the existing Atlas
admission ErrorBus owner. Any existing state.json/bamf-state.json requires explicit
resume. Resume with v1 state is not coerced to BAMF; absent BAMF pointer is held.
Even with a BAMF pointer, report unavailable accepted B13 resume validation without
reading or mutating its arrays, outbox, lease or state. No approval is inferred.

Modify parser.py to add --atlas-release-manifest(Path,None). In command.py load
requested topology before policy validation, retain the existing no-retention
guard, and route only dry-run + actual v2 topology to the new report. Print via the
existing status printer and return2 (HELD), never success/admitted. All non-dry-run
requests still use the current human/source/topology owners and remain blocked on
unavailable production authority. A manifest supplied without v2 selection rejects;
never silently ignore or reinterpret it as C07's distinct lease-scope file.

Create mirrored test_bamf_preflight.py. First fail against missing flag/report.
Use the actual repository bamf-0.2.json and real CLI entry. Assert HELD2, actual
architecture/digest, flags/prefetch values, zero updates and no created run dir;
missing/policy-conflicting/symlink manifest refusal; read-only real manifest hashing
without claiming source qualification; v1 saved state not coerced on resume; and
no human optimizer path reached. A fresh process blocking MLX imports exercises
this CLI preflight and verifies complete temporary tree bytes/mtime unchanged.
Run current CLI selection and existing Atlas-command contracts, then structure,
governance, architecture/docs/error/hygiene/diff checks against70e37ae2.

This does NOT complete #522. Production create/resume, saved admission-policy
persistence/conflicting override proof and actual A12/B13 issuer/loader integration
remain required. No new policy store or duplicate release authority is invented.
The initial reviewer facility failed with workspace-credit exhaustion. That
EGM_PENDING observation is superseded for the bounded increment by the fresh
independent review recorded in current-preflight-review.md. Production acceptance
remains open; same-context review never substitutes for independent review.
