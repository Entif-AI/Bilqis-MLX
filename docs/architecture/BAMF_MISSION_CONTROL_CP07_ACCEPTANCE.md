# BAMF Mission Control CP07 disposable acceptance

CP07 joins the existing CP01–CP06 surfaces without granting Mission Control
ownership of a learner, optimizer, checkpoint, or source record. The acceptance
tests use only temporary directories and a fixture-scoped generation-zero C11
creation. They do not train a model or launch a production learner.

## Verified integration paths

`test_cp07_process.py` starts the Python CP01 entrypoint as a separate process,
attaches through the Unix socket with a non-Electron client, and queries a CP06
SQLite index with bounded CP03 requests. It authenticates a disposable accepted
BAMF generation, binds its exact run/generation/optimizer identities into a
partial CP02 snapshot, and adds explicitly fixture-backed capability and episode
records for cross-link traversal. The test checks current and historical/as-of
queries, crashes an independent client and the control-plane process, verifies
the run pointer remains unchanged, and reconnects to the same accepted run.
Deleting or corrupting the CP06 index makes queries fail closed without hiding
the healthy learner. Rebuilding from the same source records reproduces the
literal bounded query results. The historical domain records in this test are
fixtures, not a claim of production historical-record extraction.

`test_cp07_events.py` joins a CP03 snapshot to live CP04 delivery, sends typed
lesson, candidate, capability, and resource samples, disconnects a client, and
replays the retained interval using an exact cursor. CP06 ingests each verified
payload with its envelope and deduplicates retransmission. A lagging projection
reports `STALE`; an expired or restarted stream requires a fresh snapshot. The
publisher in this test is the explicit CP02 fixture adapter, not an automatic
learner event hook.

`test_native_source.py` exercises the production-source boundary directly. It
starts from the accepted BAMF pointer, authenticates the exact content-addressed
manifest, acceptance binding, run identity, teacher state and native outbox for
each generation, then walks the v3 parent-manifest plus parent-acceptance chain
without scanning for convenient files. Current `BAMF_C16_3_ACCEPTED` events are
validated against the persisted C03 teacher-visit identity before they become
CP02 episode, candidate and capability records. Rejection-only
`BAMF_CANDIDATE_REJECTED` journal rows are accepted only when their deterministic
event identity, content-addressed rejection authority and content-addressed
rejection receipt all verify against the already authenticated accepted
generation. Rejections therefore remain visible without pretending they advanced
the learner generation.

CP04 now refreshes that authenticated native source before subscription and on
the heartbeat path. The first successful read establishes the service-local
snapshot frontier; only later accepted/rejected native facts become live deltas.
The custody layer's deliberate pointer-change rejection is treated as a transient
read race and retried on the next heartbeat, while every other authentication
failure remains fail-closed. Native event identity is retained for the owning
candidate event and deterministic child identities are derived for its episode
and capability projections.

CP06 also exposes `rebuild_from_bamf()`. The full CP02 tuple is materialized from
authenticated native artifacts before the existing atomic temporary-index swap,
so a failed ancestor/acceptance validation cannot destroy an already usable
projection. The acceptance witness deletes and rebuilds the disposable database,
compares the resulting historical/current records, and proves that tampering an
ancestor acceptance fails while the prior CP06 index remains readable.

`test_cp07_commands.py` invokes C11's accepted dry-run and human-gated genesis
code within the existing disposable test context. It admits one generation-zero
creation through CP05, uses the production command manager and durable worker
fact sequence, simulates a lost acknowledgement, reconciles the operation by ID,
and verifies terminal receipt/postcondition and its CP04 reference. A repeated
request and service restart never dispatch a second effect. The resulting
generation and optimizer step are both zero. The test uses a deterministic
fixture launcher instead of spawning a production trainer process.

## Standalone query attachment

The Python entrypoint accepts an optional `--projection-db PATH` alongside
`--run-dir` and `--socket`. The database must already be a valid CP06 index
created from accepted CP02 records. Each query reopens that index, so deletion,
corruption, and an operator-triggered rebuild are visible without restarting
the service. The option does not create a new source of truth, reconstruct
missing receipts, or silently create a fresh empty index.

Example for an existing local disposable projection:

```sh
python3 -m bilqis_mlx.control_plane \
  --run-dir /path/to/disposable-run \
  --socket /path/to/cp.sock \
  --projection-db /path/to/projection.sqlite3
```

## Remaining production acceptance boundaries

The production-source adapter now demonstrates automatic CP04 publication for
the current accepted C16.3 visit/candidate/capability path and for authenticated
rejection-only events, plus CP06 reconstruction from the accepted BAMF artifact
chain. Two source-contract debts remain explicit rather than being filled with
synthetic values:

1. Native C16.3 accepted/rejection artifacts do not carry an authenticated
   wall-clock visit interval. CP02 therefore uses the accepted generation as a
   source-owned logical materialization coordinate and marks those episode,
   candidate and capability projections `PARTIAL`; it does not claim a measured
   wall-clock timestamp.
2. The accepted BAMF bundle does not presently expose a semantically unambiguous
   one-to-one source for all three CP02 `GenerationManifest/v1` digest fields, and
   no authenticated producer currently supplies the CP02 resource sample's
   memory/budget/disk/rate facts. Historical generation-manifest and resource
   queries therefore carry explicit `UNKNOWN` markers instead of aliasing a
   convenient digest or treating bundle size as machine disk usage.

Those gaps are now visible data-contract debt rather than hidden fixture
coverage. Keep #1055 open until the owning source contracts exist or CP02 is
versioned to represent them without semantic distortion, and until the remaining
native event families required by CP04 have authoritative producers.
