"""Human-facing MLX operator commands; live training still gated by proof."""
from .presentation.operator_cli.inspection import (
    _qualification_scope,
    _latest_session_stop,
    _executable_release_summary,
    _inspect,
    _print_status,
    status,
)
from .presentation.operator_cli.preflight import (
    _source_paths,
    _boolean_revision_preflight,
    preflight,
)
from .presentation.operator_cli.parser import (
    _add_boolean_profile_args,
    parse_args,
)
from .presentation.operator_cli.lifecycle import (
    _guard_independent_no_retention,
    _report_retention_plan,
    _timing_context,
    _report_timing_trace,
    _human_sigint_guard,
    _experiment_budget,
)
from .presentation.operator_cli.terminal import (
    human_stop_summary,
    _prepare_live_board,
    _render_stopped_board,
    _report_operator_blocked,
)
from .presentation.operator_cli.explain import (
    _explain_code,
)
from .presentation.operator_cli.command import (
    dashboard,
    diagnostics,
    _main,
    main,
)
from .presentation.operator_cli.settings import (
    ROOT, DEFAULT_RUN, GRADE_A_MANIFEST, LEGACY_ROOT, ORIGINAL_CHECKPOINT,
)


if __name__ == "__main__":
    raise SystemExit(main())
