"""Three grade pointers to one student still cast three votes."""
import hashlib
import unittest
from bilqis_mlx.champions import Checkpoint
from bilqis_mlx.teacher_votes import roster,unique_inference_targets,tally


def cp(s):
    return Checkpoint(hashlib.sha256(s.encode()).hexdigest(),s+".pt",100,True)


class TeacherVoteTests(unittest.TestCase):
    def test_grade_votes_accumulate_but_inference_does_not_duplicate(self):
        shared=cp("multiple")
        solo=cp("single")
        r=roster({"A":shared,"B":solo,"C":shared,"D":shared},
                 ("A","B","C","D","E"),"E")
        self.assertEqual([v.grade for v in r],["A","B","C","D"])
        self.assertEqual(len(unique_inference_targets(r)),2)
        result=tally(r,{shared.sha256:"YES",solo.sha256:"NO"})
        self.assertEqual(result,{"NO":1,"YES":3})
        with self.assertRaisesRegex(ValueError,"BALLOTS_NOT_COMPLETE"):
            tally(r,{shared.sha256:"YES"})


if __name__=="__main__":
    unittest.main()
