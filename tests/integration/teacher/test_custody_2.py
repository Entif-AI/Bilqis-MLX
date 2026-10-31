"""Teacher integration contracts; original evidence and boundaries preserved."""
from bilqis_mlx.state_dag import read_generation
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch
import numpy as np
from bilqis_mlx import trainer as storage
from tests.integration.teacher.fixtures import TeacherFixture


class CustodyTests(TeacherFixture, unittest.TestCase):
    def test_old_model_metadata_222_never_overrides_expanded_graph_vocabulary(self):
        from bilqis_mlx.semantics.abi import HISTORICAL_PREFIX_SIZE
        actual=len(self.fixture.graph["tokens"])
        self.assertGreater(actual,HISTORICAL_PREFIX_SIZE)
        # Deliberately reconstruct a historical pre-fix *receipt* in a
        # disposable run. New numeric admissions already set the live size.
        school=storage._state_from_json(
            self.receipt["school"],self.schedule_program)
        stale=storage._advance(
            self.fixture.root,
            {**self.receipt,"config":{**self.receipt["config"],
                         "vocab_size":HISTORICAL_PREFIX_SIZE}},
            school,persist=False)
        stale=storage._persist(self.fixture.root,storage._with_delivery_outbox(
            stale,({"event":"SYNTHETIC_STALE_VOCAB_STATE",
                    "generation":stale["generation"]},)))
        self.assertEqual(stale["config"]["vocab_size"],HISTORICAL_PREFIX_SIZE)
        before=(self.receipt["school"]["current_student"],
                int(self.fixture.optimizer.state["step"].item()))
        with redirect_stdout(io.StringIO()):
            corrected=storage._reconcile_vocabulary_metadata(
                self.fixture.root,stale,self.course,self.fixture.params,
                self.fixture.optimizer,self.fixture.graph)
            _,own,_,reloaded=self.resume()
        self.assertEqual(corrected,reloaded)
        self.assertEqual(corrected["config"]["vocab_size"],actual)
        self.assertEqual(corrected["school"]["current_student"],before[0])
        self.assertEqual(int(own.state["step"].item()),before[1])
        self.assertEqual(corrected["generation"],stale["generation"]+1)
        self.assertEqual(read_generation(self.fixture.root, stale["generation"])[
                          "config"]["vocab_size"],HISTORICAL_PREFIX_SIZE)
        self.assertEqual(storage._reconcile_vocabulary_metadata(
            self.fixture.root,corrected,self.course,self.fixture.params,
            self.fixture.optimizer,self.fixture.graph),corrected)

    def test_rejected_candidate_keeps_parent_and_adamw_byte_identical(self):
        baseline={name:np.asarray(value).copy()
                  for name,value in self.fixture.params.items()}
        moments={name:{k:np.asarray(v).copy() for k,v in cell.items()}
                 for name,cell in self.fixture.optimizer.state.items()
                 if isinstance(cell,dict)}
        before_step=int(self.fixture.optimizer.state["step"].item())
        real_decider=storage.decide_learning_trial

        def forced_rejection(*args,**kwargs):
            decision=real_decider(*args,**kwargs)
            # Test the transaction path, not invented regression evidence.
            return {**decision,"decision":"REJECT",
                    "reason":"FIXTURE_FORCED_TRANSACTION_REJECTION"}

        with patch('bilqis_mlx.learning.learning_experiment.decide',
                          side_effect=forced_rejection),redirect_stdout(io.StringIO()):
            result=self.visit()
        event=result["_pending_visit_events"][-1]
        self.assertEqual(event["candidate_retention"]["decision"],"REJECT")
        self.assertEqual(event["retained_optimizer_updates"],0)
        self.assertEqual(event["teacher_reward"],0.)
        self.assertEqual(int(self.fixture.optimizer.state["step"].item()),before_step)
        self.assertLess(event["context_teacher_credit"]["teacher_context_reward"],0)
        for name,value in baseline.items():
            np.testing.assert_array_equal(np.asarray(self.fixture.params[name]),value)
            for kind,original in moments[name].items():
                np.testing.assert_array_equal(
                    np.asarray(self.fixture.optimizer.state[name][kind]),original)
        self.assertGreater(result["teacher"]["causal_experiment"]["events"],0)
