"""Authority-preserving C10 projections from accepted production owners."""
from .akasha_outbox.events import _claim_owner_payload_issuer
from .owner_generation_projection import build_generation_adapters
from .owner_package_projection import build_package_adapters
from .owner_projection_source import build_accepted_source_loader


_issue_owner_payload = _claim_owner_payload_issuer()
del _claim_owner_payload_issuer

_load_accepted_source, _require_accepted_source = build_accepted_source_loader()
events_from_accepted_bamf_generation, append_accepted_bamf_generation = (
    build_generation_adapters(
        _issue_owner_payload, _load_accepted_source, _require_accepted_source))
event_from_public_package_export, append_public_package_export = (
    build_package_adapters(_issue_owner_payload))

del _issue_owner_payload
del _load_accepted_source
del _require_accepted_source
del build_accepted_source_loader
del build_generation_adapters
del build_package_adapters


__all__ = (
    "append_accepted_bamf_generation",
    "append_public_package_export",
    "event_from_public_package_export",
    "events_from_accepted_bamf_generation",
)
