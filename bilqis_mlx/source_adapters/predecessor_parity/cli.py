'Read-only teaching contract recovered from School50 v10, not a new grade.\n\nThe frozen Grade A course is untouched. Source-grounded numeric constructions,\ntrue/false assertions, and counterexamples share one underlying arithmetic\nexpression. Acquisition replay deliberately repeats *taught* questions;\ndevelopment and sealed source expressions remain reserved and are not used for\ncandidate selection. No training, qualification, or admission occurs here.'
import json
from pathlib import Path
from ...paths import REPO_ROOT
from .plan import build_plan, validate_plan
from .report import audit_summary

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path,
                        default=REPO_ROOT / "vendor" / "legacy-v16")
    args = parser.parse_args(argv)
    plan = build_plan(args.legacy_root)
    validate_plan(plan, args.legacy_root)
    print(json.dumps(audit_summary(plan), sort_keys=True, indent=2))
