"""Local-only standalone CP01 service over a Unix-domain socket."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import socketserver
import stat
from uuid import uuid4

from bilqis_mlx.errors import ErrorBus, SCHOOL

from .contracts import (
    ControlPlaneState, ERROR_SCHEMA,
    HANDSHAKE_SCHEMA,
    HEALTH_SCHEMA,
    PROTOCOL_VERSION,
    ServiceIdentity,
    SessionIdentity,
)
from .discovery import discover_learner


MAX_REQUEST_BYTES = 64 * 1024
MAX_UNIX_SOCKET_PATH_BYTES = 100


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_CONTROL_PLANE.INVALID, reason=reason)


def _socket_identity(path: Path) -> tuple[int, int] | None:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISSOCK(observed.st_mode):
        return None
    return observed.st_dev, observed.st_ino


def _unlink_socket_if_identity(
        path: Path, identity: tuple[int, int] | None) -> bool:
    if identity is None or _socket_identity(path) != identity:
        return False
    path.unlink()
    return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prepare_socket_path(path: Path) -> None:
    if len(os.fsencode(str(path))) > MAX_UNIX_SOCKET_PATH_BYTES:
        _invalid("CONTROL_PLANE_SOCKET_PATH_TOO_LONG")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(observed.st_mode):
        _invalid("CONTROL_PLANE_SOCKET_PATH_OCCUPIED")
    observed_identity = (observed.st_dev, observed.st_ino)
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(0.1)
        probe.connect(str(path))
    except (ConnectionRefusedError, FileNotFoundError):
        if _socket_identity(path) != observed_identity:
            _invalid("CONTROL_PLANE_SOCKET_CHANGED_DURING_STARTUP")
        _unlink_socket_if_identity(path, observed_identity)
        return
    finally:
        probe.close()
    _invalid("CONTROL_PLANE_SOCKET_ALREADY_ACTIVE")


class _ThreadedUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class _RequestHandler(socketserver.StreamRequestHandler):
    def _read_request(self) -> tuple[dict | None, str | None]:
        raw = self.rfile.readline(MAX_REQUEST_BYTES + 2)
        if not raw:
            return None, None
        if len(raw) > MAX_REQUEST_BYTES + 1:
            return None, "CONTROL_PLANE_REQUEST_TOO_LARGE"
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "CONTROL_PLANE_REQUEST_INVALID"
        if not isinstance(payload, dict):
            return None, "CONTROL_PLANE_REQUEST_INVALID"
        return payload, None

    def _write(self, payload: dict) -> None:
        self.wfile.write(json.dumps(
            payload, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
        self.wfile.flush()

    def handle(self) -> None:
        service = self.server.control_plane
        request, error = self._read_request()
        if error is not None:
            self._write(service.rejected_handshake(error))
            return
        if request is None:
            return
        response, session = service.handshake(request)
        self._write(response)
        if session is None:
            return
        while True:
            request, error = self._read_request()
            if request is None:
                if error is not None:
                    self._write(service.rejected_request(session, error))
                return
            self._write(service.dispatch(session, request))


class ControlPlaneService:
    def __init__(self, run_dir: Path, socket_path: Path):
        self.run_dir = Path(run_dir).expanduser().resolve()
        self.socket_path = Path(socket_path).expanduser().resolve()
        _prepare_socket_path(self.socket_path)
        self.identity = ServiceIdentity(
            service_id=str(uuid4()),
            pid=os.getpid(),
            started_at=_utc_now(),
            socket_path=str(self.socket_path),
            run_dir=str(self.run_dir),
        )
        self._service_state = ControlPlaneState.HEALTHY
        self._socket_identity: tuple[int, int] | None = None
        server = _ThreadedUnixServer(
            str(self.socket_path), _RequestHandler, bind_and_activate=False)
        bound_identity = None
        try:
            server.server_bind()
            bound_identity = _socket_identity(self.socket_path)
            if bound_identity is None:
                _invalid("CONTROL_PLANE_SOCKET_BIND_INVALID")
            os.chmod(self.socket_path, 0o600)
            server.server_activate()
        except OSError as error:
            server.server_close()
            _unlink_socket_if_identity(self.socket_path, bound_identity)
            try:
                _invalid("CONTROL_PLANE_SOCKET_BIND_FAILED")
            except Exception as typed:
                raise typed from error
        except Exception:
            server.server_close()
            _unlink_socket_if_identity(self.socket_path, bound_identity)
            raise
        self._server = server
        self._socket_identity = bound_identity
        self._server.control_plane = self

    def _learner(self):
        return discover_learner(self.run_dir)

    def rejected_handshake(self, reason: str) -> dict:
        return {
            "schema": HANDSHAKE_SCHEMA,
            "accepted": False,
            "state": ControlPlaneState.CONNECTING.value,
            "reason": reason,
            "protocol_version": PROTOCOL_VERSION,
            "service": self.identity.to_record(),
        }

    def handshake(self, request: dict) -> tuple[dict, SessionIdentity | None]:
        if request.get("type") != "handshake":
            return self.rejected_handshake("CONTROL_PLANE_HANDSHAKE_REQUIRED"), None
        version = request.get("protocol_version")
        client_id = request.get("client_id")
        if not isinstance(client_id, str) or not client_id:
            return self.rejected_handshake("CONTROL_PLANE_CLIENT_ID_REQUIRED"), None
        if version != PROTOCOL_VERSION:
            return ({
                **self.rejected_handshake("CONTROL_PLANE_PROTOCOL_INCOMPATIBLE"),
                "state": ControlPlaneState.INCOMPATIBLE_VERSION.value,
            }, None)
        session = SessionIdentity(
            str(uuid4()), client_id, self.identity.service_id)
        learner = self._learner()
        return ({
            "schema": HANDSHAKE_SCHEMA,
            "accepted": True,
            "state": learner.state.value,
            "protocol_version": PROTOCOL_VERSION,
            "service": self.identity.to_record(),
            "session": session.to_record(),
            "learner": learner.to_record(),
        }, session)

    def _health(self, session: SessionIdentity, surface: str) -> dict:
        learner = self._learner()
        overall = (
            self._service_state
            if self._service_state is not ControlPlaneState.HEALTHY
            else learner.state)
        return {
            "schema": HEALTH_SCHEMA,
            "surface": surface,
            "state": overall.value,
            "service_state": self._service_state.value,
            "service_live": True,
            "service_ready": self._service_state is ControlPlaneState.HEALTHY,
            "learner_ready": learner.ready,
            "learner_active": learner.operator_active,
            "service": self.identity.to_record(),
            "session": session.to_record(),
            "learner": learner.to_record(),
        }

    def rejected_request(self, session: SessionIdentity, reason: str) -> dict:
        return {
            "schema": ERROR_SCHEMA,
            "accepted": False,
            "state": ControlPlaneState.HEALTHY.value,
            "reason": reason,
            "service": self.identity.to_record(),
            "session": session.to_record(),
        }

    def dispatch(self, session: SessionIdentity, request: dict) -> dict:
        surface = request.get("type")
        if surface in {"health", "readiness", "liveness"}:
            return {**self._health(session, surface), "accepted": True}
        return self.rejected_request(
            session, "CONTROL_PLANE_CP01_OPERATION_UNSUPPORTED")

    def serve_forever(self) -> None:
        try:
            self._server.serve_forever(poll_interval=0.05)
        finally:
            self.server_close()

    def prepare_restart(self) -> None:
        """Expose explicit graceful-restart intent without inferring it from errno."""
        self._service_state = ControlPlaneState.SERVICE_RESTARTING

    def shutdown(self, *, restarting: bool = False) -> None:
        if restarting:
            self.prepare_restart()
        self._server.shutdown()

    def server_close(self) -> None:
        self._server.server_close()
        _unlink_socket_if_identity(self.socket_path, self._socket_identity)
        self._socket_identity = None
