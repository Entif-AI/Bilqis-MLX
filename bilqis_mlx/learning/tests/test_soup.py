"""The same complete checkpoint can represent multiple grades without copies."""
import hashlib
import unittest
import numpy as np
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.soup import weighted_teacher


def cp(label):
    return Checkpoint(hashlib.sha256(label.encode()).hexdigest(),label+".pt",100,True)


class WeightedSoupTests(unittest.TestCase):
    def test_one_shared_checkpoint_gets_threefold_weight_and_no_adamw(self):
        one=cp("three-grades")
        two=cp("one-grade")
        grade_pointers={"A":one,"B":two,"C":one,"D":one}
        models={one.sha256:{"kernel":np.array([1,2],dtype=np.float32)},
                two.sha256:{"kernel":np.array([5,6],dtype=np.float32)}}
        soup=weighted_teacher(grade_pointers,models)
        np.testing.assert_array_equal(soup.weights["kernel"],np.array([2,3],dtype=np.float32))
        self.assertEqual(soup.contributor_multiplicity,{one.sha256:3,two.sha256:1})
        self.assertIsNone(soup.optimizer)
        self.assertEqual(soup.kind,"FROZEN_TEACHER_WEIGHTS_ONLY")

    def test_missing_or_incompatible_model_blocks_soup(self):
        one=cp("1")
        two=cp("2")
        with self.assertRaisesRegex(ValueError,"MISSING_CHAMPION"):
            weighted_teacher({"A":one,"B":two},
                             {one.sha256:{"x":np.array([1],dtype=np.float32)}})
        with self.assertRaisesRegex(ValueError,"SHAPE_MISMATCH"):
            weighted_teacher({"A":one,"B":two},
              {one.sha256:{"x":np.array([1],dtype=np.float32)},
               two.sha256:{"x":np.array([1,2],dtype=np.float32)}})
        with self.assertRaisesRegex(ValueError,"NONFP32"):
            weighted_teacher({"A":one},
                             {one.sha256:{"x":np.array([1],dtype=np.float16)}})


if __name__ == "__main__":
    unittest.main()
