# C10.1 | Append-only Akasha event stream and idempotent outbox

Issue #519, parent C10 #378. Lane C branch
`codex/bamf02-c-runtime`, reviewed unified baseline
`6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
Implementation commit:
`e20003a5511562212d33371e9cf54eb26839cf9d`.
Draft PR #550 remains human-controlled and unmerged.

## Exact owned behavior

- `bilqis.c10.akasha-event/v1` binds a stable eventID to
  canonical payload digest, source receipt, event kind,
  subject and source/effective/observed/recorded times.
  A forged eventID, payload digest or required typed field
  fails before storage.
- Seven internal-only typed projections are supported:
  source correction, revalidation, requalification,
  capability graduation, motif candidate, process fault
  and checkpoint publication. C10.2 owns external
  privacy/redaction and public visibility.
- The SQLite WAL outbox has immutable event rows and
  append-only delivery-attempt rows. Database triggers
  reject UPDATE/DELETE of historical event or delivery
  records. Identical enqueue/retry is idempotent;
  divergent eventID/attempt receipts fail closed.
  Restart readback returns only undelivered events,
  preserving source provenance.
- `events_from_c09_intent` and `append_c09_intent`
  bridge signed C09 source corrections and held learned
  capabilities to C10's stable internal eventIDs.
  The source signature is checked against the
  host-provisioned authority registry before enqueue.
  Repeated C09 enqueue produces no duplicate event.

## Verification and limits

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_akasha_outbox.py`:
**5 passed, 0 failed, 0 skipped**.
Tests cover all seven projection kinds, missing-field
rejection, stable identity, repeated enqueue, failed
then successful delivery attempts, restart recovery,
append-only trigger enforcement, malicious DB tampering,
conflicting attempts and signed C09 intent replay.

Static error-control and module-size checks found no
new C10-specific findings. This is a local durable
outbox, not an assertion of exactly-once network
transport. A future Akasha receiver must deduplicate
by eventID. Actual SKOS projection, privacy/prefix
filtering, source-owner key provisioning, C10.2/.3
and parent integration remain separate gates.
Independent EGM is pending. No live learner,
private source, checkpoint, external publication
or network delivery occurred.
