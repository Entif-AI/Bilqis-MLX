'Read-only teaching contract recovered from School50 v10, not a new grade.\n\nThe frozen Grade A course is untouched. Source-grounded numeric constructions,\ntrue/false assertions, and counterexamples share one underlying arithmetic\nexpression. Acquisition replay deliberately repeats *taught* questions;\ndevelopment and sealed source expressions remain reserved and are not used for\ncandidate selection. No training, qualification, or admission occurs here.'
from .source_adapters.predecessor_parity.contracts import SCHEMA, PREDECESSOR, STAGE_ORDER, REQUIRES, _digest
from .source_adapters.predecessor_parity.source import _source_stack, _answer_heads
from .source_adapters.predecessor_parity.lessons import _row, _native_output, _pair
from .source_adapters.predecessor_parity.plan import _build, build_plan, validate_plan
from .source_adapters.predecessor_parity.validation import _validate_structure, eligible_stage
from .source_adapters.predecessor_parity.teacher import predecessor_teaching_batch, predecessor_instruction_choice
from .source_adapters.predecessor_parity.report import head_bindings, audit_summary
from .source_adapters.predecessor_parity.cli import main


if __name__ == "__main__":
    main()
