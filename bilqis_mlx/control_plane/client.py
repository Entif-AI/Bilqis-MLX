"""Small CP01 Unix-socket client used by CLI/Electron-equivalent fixtures."""
from __future__ import annotations

import json
from pathlib import Path
import socket

from bilqis_mlx.errors import ErrorBus, SCHOOL

from .contracts import ControlPlaneState, HANDSHAKE_SCHEMA, PROTOCOL_VERSION


MAX_RESPONSE_BYTES = 64 * 1024


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_CONTROL_PLANE.INVALID, reason=reason)


class ControlPlaneClient:
    def __init__(
        self, socket_path: Path, *, client_id: str = "local-client",
        protocol_version: str = PROTOCOL_VERSION, timeout: float = 2.0,
    ):
        self.socket_path = Path(socket_path)
        self.client_id = client_id
        self.protocol_version = protocol_version
        self.timeout = timeout
        self.state = ControlPlaneState.DISCONNECTED
        self._socket: socket.socket | None = None
        self._stream = None

    def _send(self, payload: dict) -> dict:
        if self._stream is None:
            _invalid("CONTROL_PLANE_CLIENT_DISCONNECTED")
        self._stream.write(json.dumps(
            payload, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
        self._stream.flush()
        raw = self._stream.readline(MAX_RESPONSE_BYTES + 2)
        if not raw or len(raw) > MAX_RESPONSE_BYTES + 1:
            _invalid("CONTROL_PLANE_RESPONSE_INVALID")
        try:
            response = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _invalid("CONTROL_PLANE_RESPONSE_INVALID")
        if not isinstance(response, dict):
            _invalid("CONTROL_PLANE_RESPONSE_INVALID")
        return response

    def _validate_handshake(self, response: dict) -> None:
        if (response.get("schema") != HANDSHAKE_SCHEMA
                or type(response.get("accepted")) is not bool):
            _invalid("CONTROL_PLANE_HANDSHAKE_INVALID")
        if not response["accepted"]:
            return
        service = response.get("service")
        session = response.get("session")
        if (not isinstance(service, dict) or not isinstance(session, dict)
                or response.get("protocol_version") != self.protocol_version
                or service.get("protocol_version") != self.protocol_version
                or session.get("protocol_version") != self.protocol_version
                or not isinstance(service.get("service_id"), str)
                or not service["service_id"]
                or session.get("service_id") != service["service_id"]
                or session.get("client_id") != self.client_id
                or not isinstance(session.get("session_id"), str)
                or not session["session_id"]):
            _invalid("CONTROL_PLANE_HANDSHAKE_IDENTITY_INVALID")

    def connect(self) -> dict:
        self.close()
        self.state = ControlPlaneState.CONNECTING
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        try:
            connection.connect(str(self.socket_path))
            self._socket = connection
            self._stream = connection.makefile("rwb")
            response = self._send({
                "type": "handshake",
                "protocol_version": self.protocol_version,
                "client_id": self.client_id,
            })
        except PermissionError:
            connection.close()
            self._socket = None
            self._stream = None
            self.state = ControlPlaneState.UNAUTHORIZED
            raise
        except Exception:
            connection.close()
            self._socket = None
            self._stream = None
            self.state = ControlPlaneState.DISCONNECTED
            raise
        self._validate_handshake(response)
        self.state = ControlPlaneState(response["state"])
        if not response.get("accepted"):
            self.close(preserve_state=True)
        return response

    def request(self, surface: str) -> dict:
        if self._stream is None:
            _invalid("CONTROL_PLANE_CLIENT_DISCONNECTED")
        response = self._send({"type": surface})
        if "state" in response:
            self.state = ControlPlaneState(response["state"])
        return response

    def close(self, *, preserve_state: bool = False) -> None:
        if self._stream is not None:
            self._stream.close()
        if self._socket is not None:
            self._socket.close()
        self._stream = None
        self._socket = None
        if not preserve_state:
            self.state = ControlPlaneState.DISCONNECTED

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_exc):
        self.close()
