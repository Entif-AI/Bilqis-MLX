"""Private stdio broker exposing accepted CP01 state to Electron main only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from bilqis_mlx.control_plane import ControlPlaneClient
from bilqis_mlx.control_plane.contracts import ControlPlaneState, PROTOCOL_VERSION
from bilqis_mlx.mission_control.query_contracts import QUERY_PAGE_SCHEMA, QueryRequest
from bilqis_mlx.paths import active_run_dir


_CLIENT_ID = "mission-control-electron"
MAX_BROKER_REQUEST_BYTES = 64 * 1024
QUERY_ERROR_SCHEMA = "bamf.gui07.query-error/v1"


def _socket_path() -> Path:
    configured = os.environ.get("BILQIS_CONTROL_PLANE_SOCKET", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    run_dir = active_run_dir().expanduser().resolve()
    return run_dir.parent / f".{run_dir.name}.control-plane.sock"


def _public_status(payload: dict, *, connected: bool) -> dict:
    learner = payload.get("learner") if isinstance(payload.get("learner"), dict) else {}
    return {
        "schemaVersion": "bamf.gui20.cp01-status/v1",
        "state": payload.get("state", "disconnected"),
        "protocolVersion": payload.get("protocol_version", PROTOCOL_VERSION),
        "serviceLive": bool(payload.get("service_live", connected)),
        "serviceReady": bool(payload.get("service_ready", connected)),
        "learnerReady": bool(payload.get("learner_ready", learner.get("state") == "healthy")),
        "learnerActive": learner.get("operator_active"),
    }


class ElectronBridge:
    def __init__(self) -> None:
        self.client: ControlPlaneClient | None = None

    def connect(self) -> dict:
        self.disconnect()
        client = ControlPlaneClient(_socket_path(), client_id=_CLIENT_ID)
        try:
            payload = client.connect()
        except Exception:
            state = client.state
            client.close(preserve_state=True)
            if state is ControlPlaneState.CONNECTING:
                state = ControlPlaneState.DISCONNECTED
            return _public_status({"state": state.value}, connected=False)
        if not payload.get("accepted"):
            client.close(preserve_state=True)
            return _public_status(payload, connected=False)
        self.client = client
        return _public_status(payload, connected=True)

    def status(self) -> dict:
        if self.client is None:
            return _public_status({}, connected=False)
        return _public_status(self.client.request("health"), connected=True)

    def query(self, payload: dict) -> dict:
        if self.client is None:
            return {"schema": QUERY_ERROR_SCHEMA, "accepted": False,
                    "reason": "CONTROL_PLANE_NOT_CONNECTED"}
        request = QueryRequest.from_mapping(payload)
        response = self.client.query(request)
        if response.get("schema") != QUERY_PAGE_SCHEMA or not response.get("accepted"):
            reason = response.get("reason")
            return {"schema": QUERY_ERROR_SCHEMA, "accepted": False,
                    "reason": reason if isinstance(reason, str) and reason else
                    "CONTROL_PLANE_QUERY_UNAVAILABLE"}
        return {key: value for key, value in response.items()
                if key not in {"service", "session"}}

    def disconnect(self) -> dict:
        if self.client is not None:
            self.client.close()
            self.client = None
        return _public_status({}, connected=False)


def _reply(identifier, *, result=None, error=None) -> None:
    payload = {"id": identifier, "ok": error is None}
    if error is None:
        payload["result"] = result
    else:
        payload["error"] = error
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    bridge = ElectronBridge()
    for raw in sys.stdin:
        request = None
        if len(raw) > MAX_BROKER_REQUEST_BYTES:
            _reply(None, error="BAMF_GUI20_BROKER_REQUEST_INVALID")
            continue
        try:
            request = json.loads(raw)
            identifier = request["id"]
            operation = request["op"]
            if type(identifier) is not int or operation not in {
                    "connect", "status", "disconnect", "query"}:
                raise ValueError
            result = (bridge.query(request.get("query")) if operation == "query"
                      else getattr(bridge, operation)())
        except Exception:
            _reply(request.get("id") if isinstance(request, dict) else None,
                   error="BAMF_GUI20_CP01_UNAVAILABLE")
            continue
        _reply(identifier, result=result)
    bridge.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
