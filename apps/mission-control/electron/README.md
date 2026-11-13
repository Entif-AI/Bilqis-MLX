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
define and validate the request, stable-ref, event, and response records passed
through the typed methods. GUI20 intentionally does not define a competing CP02
grammar. `ControlPlaneBridge` requires injected CP02 validators for request/event
records and applies only bounded-JSON plus credential-leak guards itself.

`createMissionControlWindow` forces `contextIsolation`, sandboxing, no Node
integration, no webviews, and normal web security even when caller options try to
weaken them. Production renderer loading is pinned to
`bamf-mc://app/index.html`; `file:`, `http:`, `https:`, `data:` and `javascript:`
documents are never privileged renderer locations. GUI01 must register the
`bamf-mc` scheme before Electron readiness and serve only its packaged renderer
assets from that origin. The scheme is registered as standard/secure without a CSP
bypass. New windows, external navigation, webview attachment, and renderer
permission requests are denied.

IPC sender trust binds all three identities: the exact BrowserWindow WebContents,
its exact top frame, and the `bamf-mc://app` origin/document. Service exceptions
are mapped to GUI20-owned safe error codes before they can cross IPC. Malformed or
credential-bearing service events are dropped at the bridge and may emit only a
non-secret violation code to a main-process diagnostic hook.

The checked-in preload entrypoint is deliberately self-contained. Electron's
sandboxed preload runtime does not load arbitrary local CommonJS modules. Tests
execute the actual preload source with a `require` shim that permits only
`electron`, which catches accidental local-module imports before GUI01 packages the
desktop app.

Run the bounded security suite with:

```bash
npm run mission-control:security:test
```

The suite is Node-only. It does not launch Electron, touch the learner, read a run
directory, or require CP01/CP02 to be present. Final GUI20 integration must still
consume the accepted CP01 and CP02 implementations and GUI01's packaged renderer
protocol handler before the issue closes. The canonical leaf and premerge commands
and the hosted portable-core workflow run this suite so CJS-only security changes
cannot bypass repository gates.
