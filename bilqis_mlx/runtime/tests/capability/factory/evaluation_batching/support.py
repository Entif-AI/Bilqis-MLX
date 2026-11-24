"""C05 #1167 fixed-school MLX batching equivalence and resource witnesses."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mlx.core as mx
from bilqis_mlx.errors import BilqisError
import bilqis_mlx.learning.source_atoms.embedding as source_embedding
import bilqis_mlx.runtime.backbone_identity as backbone_identity
from bilqis_mlx.runtime.capability_retention import (
    EvidenceKind, EvaluationCohort, case_census_digest,
    candidate_work_disposition, evaluate_capabilities,
)
from bilqis_mlx.runtime.factory_complete_solver import (
    factory_complete_solver, factory_evaluation_instrument,
)
import bilqis_mlx.runtime.factory_evaluation_batching as batching
import bilqis_mlx.runtime.factory_complete_solver as complete_solver_module
from bilqis_mlx.runtime.factory_evaluation_batching import _capacity
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch
from bilqis_mlx.runtime.factory_task_authority import FactoryTaskAuthority
from bilqis_mlx.learning.atlas_readout import AnswerPlan
from bilqis_mlx.runtime.factory_evaluation_compiler import compile_factory_evaluation_batch
from bilqis_mlx.runtime.tests.batch.factory.factory_training_bridge_support import (
    FactoryTrainingBridgeFixture,
)


class FactoryEvaluationBatchingTests(FactoryTrainingBridgeFixture):
    CAPABILITY = "A.IDENTITY"
    SEED = 37144
    EACH = 4

    def _instruments(self):
        rows = tuple(self.context.draw_rows(
            seed=self.SEED, capability=self.CAPABILITY, each=self.EACH))
        self.assertEqual(len(rows), self.EACH)
        return tuple(factory_evaluation_instrument(
            self.context, self.candidate, str(self.artifact), row,
            source_seed=self.SEED, source_each=self.EACH)
            for row in rows)

    def _instruments_for(self, capability, *, seed, each):
        rows = tuple(self.context.draw_rows(
            seed=seed, capability=capability, each=each))
        self.assertEqual(len(rows), each)
        return tuple(factory_evaluation_instrument(
            self.context, self.candidate, str(self.artifact), row,
            source_seed=seed, source_each=each)
            for row in rows)

    def _solver_pair(self, instruments):
        scalar, generation = factory_complete_solver(
            self.context, self.candidate, str(self.artifact), instruments)
        batched, batch_generation = factory_complete_solver(
            self.context, self.candidate, str(self.artifact), instruments)
        self.assertEqual(generation, batch_generation)
        return replace(scalar, contexts_for=None), batched, generation

    @staticmethod
    def _cohort(instruments):
        cases = tuple(item.case for item in instruments)
        return EvaluationCohort(
            EvidenceKind.FIXED_SCHOOL,
            cases,
            ((cases[0].capability_id, cases[0].group_id),),
            "1" * 64,
            "2" * 64,
            "3" * 64,
            "4" * 64,
            ("training-family",),
            ("training-episode",),
            case_census_digest(cases),
        )
