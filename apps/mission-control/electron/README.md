# Mission Control Electron security boundary

GUI20 owns the Electron security membrane. It does not own the Mission Control
views, the CP01 transport, or the CP02 BAMF records.

The renderer receives one frozen preload object, `window.bamfMissionControl`.
That object exposes connect/status, snapshot, event, dry-run, command, and receipt
operations through fixed IPC channels. It does not expose `ipcRenderer`, generic
send/invoke primitives, Node, filesystem, shell, process, run-directory, or service
credential access.

Electron main owns the service session. `ControlPlaneBridge` expects an adapter with
the following main-process methods:

- `connect() -> { session, publicStatus }`
- `disconnect(session)`
- `status(session)`
- `snapshot(session, request)`
- `dryRun(session, request)`
- `command(session, request)`
- `receipt(session, stableRef)`
- `subscribe(session, callback) -> unsubscribe`

The `session` value is opaque and never crosses into renderer state. CP01 should
implement the transport/version/session handshake behind this adapter. CP02 should
define the request and response records passed through the typed methods. GUI20
rejects filesystem/process-shaped request keys and credential-shaped response keys
before either can cross the Electron boundary.

`createMissionControlWindow` forces `contextIsolation`, sandboxing, no Node
integration, no webviews, and normal web security even when caller options try to
weaken them. It denies new windows, external navigation, webview attachment, and
renderer permission requests. IPC calls are also bound to the exact renderer
document URL.

Run the bounded security suite with:

```bash
npm run mission-control:security:test
```

The suite is Node-only. It does not launch Electron, touch the learner, read a run
directory, or require CP01/CP02 to be present. Final GUI20 integration must still
consume the accepted CP01 and CP02 implementations before the issue closes.
