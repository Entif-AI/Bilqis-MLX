'Neural-inert, source-bound typed composition discovery and witness accounting.\n\nThe approved Course and versioned Token Atlas supply candidate semantics.\nSource interpreters, not matching answer types, decide whether a particular\nconstruction actually works. No result of this module admits lessons or changes\nthe live model, its teacher, or historical grade release definitions.'
from .verification.coverage.contracts import SCHEMA, _digest, require_coverage_audit_budget
from .verification.coverage.discovery import (
    _TYPE, _signature, _source_dialect, discover_composition_obligations,
)
from .verification.coverage.witnesses import verify_micro_composition_witnesses
from .verification.coverage.audit import audit_pinned_micro_generator
from .verification.coverage.dependencies import affected_typed_dependency_closure
from .verification.coverage.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
