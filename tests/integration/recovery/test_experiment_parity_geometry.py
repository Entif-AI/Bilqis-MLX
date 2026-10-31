"""One read-only 6x384x24 real-geometry check, NOT a learning experiment."""
import unittest

import numpy as np

from bilqis_mlx.learning.learning_experiment import fork_student
from bilqis_mlx.runtime.mlx_parity import forward_arrays


class ParityGeometryTests(unittest.TestCase):
    def test_current_graph_sized_parity_student_and_adamw_copy(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        from bilqis_mlx.live_grade_c import registry_graph
        mx.set_default_device(mx.cpu)
        d, layers, heads = 384, 6, 24
        current_vocab = len(registry_graph()["tokens"])
        shapes = {"embedding.weight": (current_vocab,d),
                  "position.weight": (96,d), "norm.weight":(d,)}
        for index in range(layers):
            prefix=f"blocks.{index}."
            shapes.update({prefix+"n1.weight":(d,),
                           prefix+"n2.weight":(d,),
                           prefix+"qkv.weight":(3*d,d),
                           prefix+"proj.weight":(d,d),
                           prefix+"up.weight":(4*d,d),
                           prefix+"down.weight":(d,4*d)})
        self.assertEqual(sum(np.prod(value) for value in shapes.values()),
                         current_vocab*d+96*d+d+
                         layers*(2*d+3*d*d+d*d+4*d*d+4*d*d))
        parameters={name:(mx.ones(shape,dtype=mx.float32) if len(shape)==1
                          else mx.zeros(shape,dtype=mx.float32))
                    for name,shape in shapes.items()}
        optimizer=optim.AdamW(learning_rate=.00013,bias_correction=True)
        optimizer.update(parameters,{key:mx.zeros_like(value)
                                     for key,value in parameters.items()})
        mx.eval(parameters,optimizer.state)
        student,own_optimizer=fork_student(mx,parameters,optimizer)
        self.assertEqual(set(student),set(parameters))
        self.assertEqual(int(own_optimizer.state["step"].item()),1)
        self.assertEqual(int(optimizer.state["step"].item()),1)
        ids=np.array([[1,2,3,0],[2,3,4,5]],dtype=np.int32)
        logit=forward_arrays(mx,student,ids,np.array([3,4],dtype=np.int32),
                             heads=heads,layers=layers,answer_ids=[6,7])
        mx.eval(logit)
        self.assertEqual(logit.shape,(2,2))


if __name__=="__main__":
    unittest.main()
