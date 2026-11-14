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

The current implementation does **not** automatically translate all live
learner events into CP02 records or publish them into CP04. It also does not
reconstruct the full historical CP06 corpus directly from an authenticated BAMF
run's durable artifact lineage. Those production-source adapters require an
explicit contract mapping before CP07 can claim universal live-event coverage
or independent reconstruction of every historical receipt. An injected fixture
source cannot stand in for these guarantees. Keep #1055 open until that final
source integration and its end-to-end evidence are proved.
