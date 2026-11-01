"""Human operator command arguments."""
from __future__ import annotations
from pathlib import Path
import argparse
from .settings import DEFAULT_RUN


def _add_boolean_profile_args(parser) -> None:
    boolean_profile = parser.add_mutually_exclusive_group()
    boolean_profile.add_argument(
        '--full-grade-b', dest='full_grade_b', action='store_true',
        help='Use the full canonical Grade B capability set (default).')
    boolean_profile.add_argument(
        '--reduced-grade-b', '--minimal-grade-b', dest='full_grade_b',
        action='store_false',
        help='Explicitly opt into the historical reduced AND/IFF Grade B profile.')
    parser.set_defaults(full_grade_b=True)


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description="Human-facing MLX operator commands; live training still gated by proof.")
    actions=parser.add_subparsers(dest="action",required=True)
    for name in ("status","dashboard","diagnostics","train"):
        p=actions.add_parser(name)
        p.add_argument("--run-dir",type=Path,default=DEFAULT_RUN)
        if name=="train":
            from bilqis_mlx.runtime.atlas_admission import add_atlas_admission_arguments
            add_atlas_admission_arguments(p)
            p.add_argument("--legacy-code-root", type=Path,
                           help="Explicit pinned predecessor source for an independent worktree")
            p.add_argument("--champion-checkpoint", type=Path,
                           help="Explicit original checkpoint; the existing source fingerprint still applies")
            p.add_argument("--dry-run",action="store_true")
            p.add_argument("--verify-source",action="store_true",
                           help="Recheck all 216 candidate records against the pinned source (neural-inert)")
            p.add_argument("--resume",action="store_true")
            p.add_argument("--model-topology", type=Path,
                           help="Versioned ModelTopologySpec JSON; resume must match saved topology.")
            p.add_argument('--numeric-staircase', action='store_true',
                           help='Warm-start C at 0..3, grow to 6 before MUL/DIV')
            p.add_argument('--boolean-composite', action='store_true',
                           help='Neural-inertly enroll B.COMPOSITE into the current Grade-B release')
            p.add_argument('--boolean-idboolops', action='store_true',
                           help='Neural-inertly enroll inverse Boolean primitive identification into Grade B')
            _add_boolean_profile_args(p)
            retention = p.add_mutually_exclusive_group()
            retention.add_argument('--no-retention', action='store_true',
                                   help='Explicit unprotected legacy teaching (separate independent --run-dir only)')
            # Existing terminal histories from human-run sessions can still
            # be replayed without accidentally changing the retention mode.
            retention.add_argument('--experimental-retention', action='store_true',
                                   help=argparse.SUPPRESS)
            p.add_argument('--retention-probe-each', '--experiment-probe-each',
                           dest='experiment_probe_each', type=int, default=6,
                           help='Source-oracled same-cohort rows per admitted capability')
            p.add_argument('--retention-mature-max-loss', '--experiment-mature-max-loss',
                           dest='experiment_mature_max_loss', type=int, default=1,
                           help='PROVISIONAL max new wrong answers on any protected capability')
            p.add_argument('--retention-introduction-extra-loss', '--experiment-introduction-extra-loss',
                           dest='experiment_introduction_extra_loss', type=int, default=2,
                           help='Additional tolerable losses during first acquisition')
            p.add_argument('--retention-protected-cap-limit', '--experiment-protected-cap-limit',
                           dest='experiment_protected_cap_limit', type=int, default=8,
                           help='Bounded grade-stratified sentinel panel per visit')
            p.add_argument("--human-run",action="store_true",
                           help="Explicitly authorizes actual optimizer steps by the human operator")
            p.add_argument("--autonomous-curriculum", action="store_true",
                           help="After --human-run authorization, autonomously measure, teach, and remeasure factory evidence while preserving the school scheduler")
            p.add_argument(
                "--issue-349-experiment-root", type=Path,
                help="Register/enforce this run under issue #349's <=2-run, 100-GB collective experiment custody root")
            p.add_argument("--minutes",type=int,default=90)
            p.add_argument("--steps-per-visit",type=int,default=16)
            p.add_argument("--max-visits",type=int,default=0,
                           help="Optional complete visit cap (default 0: use --minutes and disk reserve)")
            p.add_argument("--timing-trace", action="store_true",
                           help="Write low-overhead nanosecond timing markers under runs/.timing-traces")
            p.add_argument("--source-prefetch-workers", type=int, choices=(0, 1, 2), default=2,
                           help="Pure host-side lesson prep workers; 2 workers + main MLX lane = 3 lanes")
            p.add_argument("--flash-mode", action="store_true",
                           help="Defer expensive assessments while training; stop owing a real assessment")
            p.add_argument("--source-teaching-enrichment", "--boolean-association-bridge",
                           dest="boolean_association_bridge", action="store_true",
                           help="Add optional source-owned lessons declared by the admitted factory release")
            p.add_argument("--batch-size",type=int,default=32)
            p.add_argument("--reserve-gib",type=float,default=100.)
            p.add_argument("--stagnation-grace-grade",type=str,default=None,
                           help="Human-authorized grade whose stagnation quarantine actuator is temporarily suppressed")
            p.add_argument("--stagnation-grace-steps",type=int,default=0,
                           help="Retained optimizer-step budget for the persisted stagnation grace")
            p.add_argument("--admit-next-grade-with-debt", action="store_true",
                           help="Human-authorized one-time next-grade admission after substantial rehabilitation; preserves unresolved prior mastery debt")
            p.add_argument("--triplets","--triples",dest="triples",action="store_true",
                           help="Global weakest-three recovery is intrinsic to the new scheduler")
    # The npm explain script is an operator contract, not an experimental
    # feature. Register it in the same CLI that npm invokes from this checkout.
    for name in ("explain", "explain-error"):
        explain = actions.add_parser(name)
        explain.add_argument(
            "code", help="Typed error, legacy error, stop reason, or blocker code")
    return parser.parse_args(argv)
