"""Local-only standalone CP01 service over a Unix-domain socket."""
from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import os
from uuid import uuid4

from .contracts import (
    ControlPlaneState, ERROR_SCHEMA,
    HANDSHAKE_SCHEMA,
    HEALTH_SCHEMA,
    PROTOCOL_VERSION,
    ServiceIdentity,
    SessionIdentity,
)
from .discovery import discover_learner
from .event_stream import EventFamily, EventStreamBroker
from .stream_transport import serve_event_subscription
from .transport import (
    _RequestHandler, _ThreadedUnixServer, _acquire_service_lock, _invalid,
    _prepare_socket_path, _release_service_lock, _socket_identity,
    _unlink_socket_if_identity,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ControlPlaneService:
    def __init__(
        self, run_dir: Path, socket_path: Path, *,
        event_retention_limit: int = 256, event_queue_limit: int = 64,
        resource_bucket_span: int = 5, event_heartbeat_seconds: float = 0.25,
    ):
        if (
            type(event_retention_limit) is not int
            or type(event_queue_limit) is not int
            or type(resource_bucket_span) is not int
            or min(
                event_retention_limit,
                event_queue_limit,
                resource_bucket_span,
            ) <= 0
            or type(event_heartbeat_seconds) not in (int, float)
            or not math.isfinite(event_heartbeat_seconds)
            or event_heartbeat_seconds <= 0
        ):
            _invalid("CONTROL_PLANE_EVENT_CONFIG_INVALID")
        self.run_dir = Path(run_dir).expanduser().resolve()
        self.socket_path = Path(socket_path).expanduser().resolve()
        self._service_lock_fd = _acquire_service_lock(self.socket_path)
        try:
            _prepare_socket_path(self.socket_path)
        except Exception:
            _release_service_lock(self._service_lock_fd)
            self._service_lock_fd = None
            raise
        self.identity = ServiceIdentity(
            service_id=str(uuid4()),
            pid=os.getpid(),
            started_at=_utc_now(),
            socket_path=str(self.socket_path),
            run_dir=str(self.run_dir),
        )
        self.events = EventStreamBroker(
            epoch_id=self.identity.service_id,
            retention_limit=event_retention_limit,
            subscriber_queue_limit=event_queue_limit,
            resource_bucket_span=resource_bucket_span,
        )
        self.event_heartbeat_seconds = event_heartbeat_seconds
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
            _release_service_lock(self._service_lock_fd)
            self._service_lock_fd = None
            try:
                _invalid("CONTROL_PLANE_SOCKET_BIND_FAILED")
            except Exception as typed:
                raise typed from error
        except Exception:
            server.server_close()
            _unlink_socket_if_identity(self.socket_path, bound_identity)
            _release_service_lock(self._service_lock_fd)
            self._service_lock_fd = None
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
            "reason": reason,
            "service_state": self._service_state.value,
            "service": self.identity.to_record(),
            "session": session.to_record(),
        }

    def dispatch(self, session: SessionIdentity, request: dict) -> dict:
        surface = request.get("type")
        if surface in {"health", "readiness", "liveness"}:
            return {**self._health(session, surface), "accepted": True}
        if surface == "event-frontier":
            return {
                **self.events.frontier().to_record(),
                "accepted": True,
                "session": session.to_record(),
            }
        return self.rejected_request(
            session, "CONTROL_PLANE_CP01_OPERATION_UNSUPPORTED")

    def publish_event(self, family: EventFamily, payload, *, event_id: str | None = None):
        """Publish one CP02-backed delta without making the stream authoritative."""
        return self.events.publish_record(family, payload, event_id=event_id)

    def flush_event_telemetry(self):
        return self.events.flush_resource_samples()

    def stream_events(
        self, session: SessionIdentity, request: dict, write_record,
    ) -> None:
        serve_event_subscription(self, session, request, write_record)

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
        _release_service_lock(self._service_lock_fd)
        self._service_lock_fd = None
