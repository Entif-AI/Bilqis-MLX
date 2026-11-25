#!/usr/bin/env bash
# Canonical repository-owned CI commands, shared by Actions and Husky.
set -euo pipefail

test_python() {
  if [[ "${BILQIS_LOCAL_CI:-0}" == 1 ]]; then
    python3 -B -m scripts.quality.bounded_python "$@"
  else
    python3 -B "$@"
  fi
}

case "${1:-}" in
  release)
    python3 -B scripts/maintenance/release_version.py --check
    ;;
  structure)
    BASE_REF="$QUALITY_BASE_REF"
    case "$BASE_REF" in
      ""|0000000000000000000000000000000000000000) BASE_REF=HEAD ;;
    esac
    python3 -B scripts/check_module_size.py --changed-from "$BASE_REF"
    python3 -B scripts/quality/check_governance_integrity.py --base-ref "$BASE_REF"
    ;;
  flow-control)
    python3 -B scripts/check_bamf_flow_control.py
    ;;
  invariant-transfer)
    python3 -B scripts/check_bamf_invariant_transfer.py
    ;;
  detached-witness)
    test_python -m unittest scripts.tests.bamf.test_checked_launch scripts.tests.bamf.test_detached_long_run
    ;;
  historical-abi)
    python3 -B scripts/check_historical_abi.py
    ;;
  legacy-semantic)
    python3 -B scripts/check_semantic_boundaries.py
    ;;
  bamf-contracts)
    test_python scripts/run_tests.py \
      bilqis_mlx/factory/tests/curriculum/test_factory_construction.py \
      bilqis_mlx/factory/tests/test_curriculum_compiler.py \
      bilqis_mlx/factory/tests/test_grade_admission.py \
      bilqis_mlx/semantics/tests/foundation/test_domain_contracts.py \
      bilqis_mlx/verification/tests/test_construction_contracts.py \
      bilqis_mlx/verification/coverage/tests \
      bilqis_mlx/source_adapters/predecessor_parity/tests/test_contracts.py \
      bilqis_mlx/factory/tests/lifecycle/test_release_outcome_contracts.py
    ;;
  architecture)
    python3 -B scripts/check_factory_architecture.py
    python3 -B scripts/quality/check_docs.py
    if [ -n "$QUALITY_BASE_REF" ]; then
      python3 -B scripts/error_control_plane.py --check --base-ref "$QUALITY_BASE_REF"
    else
      python3 -B scripts/error_control_plane.py --check
    fi
    ;;
  frontend)
    node --version
    npm ci --ignore-scripts
    npm run bamf:test
    npm run bamf:security:test
    ;;
  code-smell)
    BASE_REF="$QUALITY_BASE_REF"
    case "$BASE_REF" in
      ""|0000000000000000000000000000000000000000) BASE_REF=HEAD ;;
    esac
    python3 -B scripts/code_smell_audit.py --changed-from "$BASE_REF" \
      --check-baseline docs/evidence/development/code_smell_baseline.json
    ;;
  portable-custody)
    test_python scripts/run_tests.py \
      bilqis_mlx/learning/_teaching/tests/test_teacher_observations.py \
      bilqis_mlx/runtime/tests/teacher/test_teacher_observation_capture.py \
      bilqis_mlx/runtime/tests/teacher/test_capture_identity.py \
      bilqis_mlx/semantics/frame_codec_parts/tests \
      bilqis_mlx/runtime/operator_session/tests \
      bilqis_mlx/compatibility/live_release_parts/tests/test_providers.py \
      bilqis_mlx/runtime/tests/teacher/test_teacher_observation_replay.py \
      bilqis_mlx/runtime/tests/operator/test_qualification.py \
      bilqis_mlx/runtime/tests/model/parity/test_model_topology.py \
      bilqis_mlx/runtime/tests/model/test_topology_lifecycle.py \
      bilqis_mlx/runtime/tests/custody/test_state_archive.py \
      bilqis_mlx/learning/_retention/tests/test_whole_student_retention.py \
      scripts/tests/test_release_version.py \
      scripts/tests/test_docs.py \
      scripts/tests/test_run_tests.py \
      scripts/tests/test_run_tests_package_collision.py \
      scripts/tests/tooling/test_skos_test_policy.py \
      scripts/tests/governance/test_module_size.py \
      scripts/tests/governance/test_governance_integrity.py \
      scripts/tests/governance/test_smell_verification_reuse.py \
      scripts/tests/governance/test_abi_verification_reuse.py \
      scripts/tests/tooling/test_verification_receipts.py \
      scripts/tests/tooling/test_verification_environment.py \
      scripts/tests/tooling/test_verification_projection.py \
      scripts/tests/tooling/test_quality_workflow_evidence.py \
      scripts/tests/governance/test_pr_scope.py \
      scripts/tests/test_run_required_tests.py \
      bilqis_mlx/factory/tests/lifecycle/test_release.py \
      bilqis_mlx/factory/tests/lifecycle/test_generation.py \
      bilqis_mlx/factory/tests/curriculum/test_historical_generalization.py \
      bilqis_mlx/runtime/tests/operator/test_admission.py \
      bilqis_mlx/runtime/tests/operator/test_admission_cold_readback.py \
      scripts/tests/tooling/test_pre_push_ci.py
    ;;
  semantic-plan)
    python3 -B scripts/skos_test_policy.py plan \
      --base-ref "$SKOS_BASE_REF" \
      --github-output "$GITHUB_OUTPUT"
    ;;
  native-witness)
    test_python -m unittest scripts.tests.bamf.test_checked_witness
    ;;
  readiness)
    if [[ "${BILQIS_LOCAL_CI:-0}" == 1 ]]; then
      test_python scripts/run_required_tests.py --bamf-readiness
    else
      python3 -B -m scripts.quality.run_verified --check bamf-readiness -- python3 -B scripts/run_required_tests.py --bamf-readiness
    fi
    ;;
  semantic-diff)
    python3 -B scripts/skos_test_policy.py run --base-ref "$SKOS_BASE_REF"
    ;;
  semantic-shard)
    python3 -B scripts/skos_test_policy.py run --base-ref "$SKOS_BASE_REF" --full-shard-index "$SKOS_SHARD_INDEX" --full-shard-count 8
    ;;
  abi-scope)
    set -euo pipefail
    if [[ "$EVENT_NAME" == "workflow_dispatch" ]]; then
      echo "run=true" >> "$GITHUB_OUTPUT"
      echo "Manual dispatch: running full Semantic ABI integrity suite."
      exit 0
    fi

    run=false
    paths=$(git diff --name-only "$BASE_SHA" "$HEAD_SHA")
    while IFS= read -r path; do
      case "$path" in
        lib/ithkuil/*|\
        bilqis_mlx/semantics/*|\
        bilqis_mlx/source_adapters/*|\
        bilqis_mlx/factory/*|\
        bilqis_mlx/verification/*|\
        bilqis_mlx/diagnostics/*|\
        bilqis_mlx/_semantic_tools/*|\
        bilqis_mlx/_boolean_sources/*|\
        bilqis_mlx/_numeric_sources/*|\
        bilqis_mlx/_source_evidence/*|\
        bilqis_mlx/_release_views/*|\
        bilqis_mlx/_curriculum_compiler/*|\
        bilqis_mlx/_registry_ast/*|\
        bilqis_mlx/boolean*.py|\
        bilqis_mlx/curriculum.py|\
        bilqis_mlx/generated_assessment.py|\
        bilqis_mlx/grade_*.py|\
        bilqis_mlx/live_grade_*.py|\
        bilqis_mlx/numeric*.py|\
        bilqis_mlx/vocabulary_growth.py|\
        scripts/check_historical_abi.py|\
        scripts/check_semantic_boundaries.py|\
        scripts/tests/tooling/test_semantic_module_boundaries.py)
          run=true
          echo "Semantic ABI owned path changed: $path"
          break
          ;;
      esac
    done <<< "$paths"
    echo "run=$run" >> "$GITHUB_OUTPUT"
    if [[ "$run" != "true" ]]; then
      echo "No Semantic ABI owned paths changed; full suite is not applicable."
    fi
    ;;
  abi-contract)
    set -euo pipefail
    if [[ "${BILQIS_ABI_REQUIRE_EXTERNAL:-false}" == "true" ]]; then
      python3 -B scripts/check_historical_abi.py --require-external
    else
      python3 -B scripts/check_historical_abi.py
    fi
    python3 -B scripts/check_semantic_boundaries.py
    ;;
  abi-tests)
    test_python scripts/run_tests.py \
      bilqis_mlx/verification/tests/test_review_evidence.py \
      bilqis_mlx/factory/tests/curriculum/test_next_grade_review.py \
      bilqis_mlx/factory/tests/curriculum/test_factory_construction.py \
      bilqis_mlx/factory/tests/test_curriculum_compiler.py \
      bilqis_mlx/factory/tests/test_grade_admission.py \
      bilqis_mlx/diagnostics/tests/test_health_shadow.py \
      bilqis_mlx/diagnostics/tests/test_candidate_shadow.py \
      scripts/tests/tooling/test_semantic_module_boundaries.py \
      bilqis_mlx/semantics/tests/foundation/test_domain_contracts.py \
      bilqis_mlx/verification/tests/test_construction_contracts.py \
      bilqis_mlx/factory/tests/lifecycle/test_release_outcome_contracts.py
    ;;
  commit-subjects)
    set -euo pipefail
    if [[ "${BILQIS_LOCAL_CI:-0}" != 1 || -n "${PR_TITLE:-}" ]]; then
      python3 -B scripts/maintenance/release_version.py --validate-subject "$PR_TITLE"
    fi
    if [[ "$BASE_REF" != "main" ]]; then
      echo "Squash feature PR: the PR title is the preserved commit subject."
      exit 0
    fi
    subjects=$(python3 -B scripts/quality/pr_scope.py commits \
      --base-sha "$BASE_SHA" --head-sha "$HEAD_SHA" --head-ref "$HEAD_REF")
    while IFS=$'\t' read -r commit subject; do
      [[ -n "$commit" ]] || continue
      echo "Validating commit subject $commit"
      python3 -B scripts/maintenance/release_version.py --validate-subject "$subject"
    done <<< "$subjects"
    ;;
  local-governance)
    npm run bamf:legacy-trainer
    npm run bamf:legacy-trainer:test
    npm run bamf:invariant-transfer:test
    npm run bamf:flow-control:test
    ;;
  *) echo "Unknown CI verification group: ${1:-}" >&2; exit 2 ;;
esac
