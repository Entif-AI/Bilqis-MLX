"""Disposable synthetic FP32 mapping tests, not a model training run."""
import unittest
import numpy as np
from bilqis_mlx.runtime import mlx_parity as parity


class MlxMappingTests(unittest.TestCase):
    def test_inference_batch_rows_preserves_legacy_worst_case_memory_envelope(self):
        rows = lambda length, count=1000: [{"tokens": [1] * length}] * count
        self.assertEqual(parity.inference_batch_rows(rows(96)), 24)
        self.assertEqual(parity.inference_batch_rows(rows(48)), 48)
        self.assertEqual(parity.inference_batch_rows(rows(6)), 384)
        self.assertEqual(parity.inference_batch_rows(rows(3)), 768)

    def test_causal_forward_matches_torch_for_small_synthetic_model(self):
        import mlx.core as mx
        import torch
        from torch.nn import functional as F
        mx.set_default_device(mx.cpu)
        torch.manual_seed(123)
        dimension=12
        names={"embedding.weight":(24,dimension),"position.weight":(6,dimension),
               "norm.weight":(dimension,)}
        names.update({f"blocks.0.{name}.weight":size for name,size in {
             "n1":(dimension,),"n2":(dimension,),"qkv":(dimension*3,dimension),
             "proj":(dimension,dimension),"up":(24,dimension),"down":(dimension,24)}.items()})
        weights={k:(torch.randn(shape,dtype=torch.float32)*.05 if len(shape)>1
                    else torch.ones(shape,dtype=torch.float32)) for k,shape in names.items()}
        inp=torch.tensor([[1,2,3],[4,5,6]],dtype=torch.long)
        lengths=[2,3]
        x=F.embedding(inp,weights["embedding.weight"])+weights["position.weight"][None,:3]
        norm=lambda v,w:F.layer_norm(v,(dimension,),w,None,1e-5)
        prefix="blocks.0."
        q,k,v=F.linear(norm(x,weights[prefix+"n1.weight"]),
                       weights[prefix+"qkv.weight"]).chunk(3,dim=-1)
        q,k,v=(t.reshape(2,3,3,4).transpose(1,2) for t in (q,k,v))
        attention=F.scaled_dot_product_attention(q,k,v,is_causal=True,dropout_p=0)
        x=x+F.linear(attention.transpose(1,2).contiguous().reshape(2,3,dimension),
                     weights[prefix+"proj.weight"])
        z=F.relu(F.linear(norm(x,weights[prefix+"n2.weight"]),weights[prefix+"up.weight"]))
        x=x+F.linear(z*z,weights[prefix+"down.weight"])
        x=norm(x,weights["norm.weight"])
        h=torch.stack([x[i,n-1] for i,n in enumerate(lengths)])
        expected=F.linear(h,weights["embedding.weight"][[6,7]]).numpy()
        mlxweights={k:mx.array(t.numpy(),dtype=mx.float32) for k,t in weights.items()}
        actual=parity.forward(mx,mlxweights,inp.numpy(),lengths,heads=3,layers=1,
                              answer_ids=[6,7])
        self.assertLessEqual(float(np.max(np.abs(expected-actual))),1e-4)

    def test_native_moments_exact_map_and_no_update(self):
        import torch
        torch.manual_seed(124)
        p=torch.nn.Parameter(torch.tensor([0.2,0.3],dtype=torch.float32))
        opt=torch.optim.AdamW([p],lr=.001,betas=(.9,.95),eps=1e-8,weight_decay=.01)
        p.grad=torch.tensor([0.1,-.2])
        opt.step()  # Synthetic-only test; no saved Bilqis checkpoint involved.
        before=p.detach().clone()
        reported,mapped=parity.native_optimizer_to_mlx(
            opt.state_dict(),{"weight":p.data},parameter_order=("weight",))
        self.assertEqual(reported["moment_entries"],1)
        self.assertEqual(reported["max_moment_absolute_error"],0.0)
        self.assertEqual(reported["native_step"],1)
        self.assertTrue(torch.equal(p,before))
        self.assertFalse(reported["native_optimizer_updated"])

    def test_moment_mapping_refuses_missing_parameter_identity(self):
        import torch
        p=torch.nn.Parameter(torch.tensor([.2,.3]))
        opt=torch.optim.AdamW([p])
        p.grad=torch.ones_like(p)
        opt.step()
        with self.assertRaisesRegex(ValueError,"NOT_BIJECTIVE"):
            parity.native_optimizer_to_mlx(
                opt.state_dict(),{"weight":p.data},parameter_order=("other",))

    def test_uniform_historical_step_maps_to_scalar_and_row_counts(self):
        import mlx.core as mx
        import torch
        p=torch.nn.Parameter(torch.tensor([[.2,.3],[.4,.5]],dtype=torch.float32))
        q=torch.nn.Parameter(torch.tensor([.6,.7,.8],dtype=torch.float32))
        opt=torch.optim.AdamW([p,q],lr=.001)
        for _ in range(3):
            p.grad=torch.ones_like(p)
            q.grad=torch.ones_like(q)
            opt.step()
        counts=parity.native_uniform_step_counts(
            opt.state_dict(),{"p":p.data,"q":q.data},
            parameter_order=("p","q"),count_shapes={"p":(2,),"q":()})
        np.testing.assert_array_equal(np.asarray(counts["p"]),np.array([3,3],dtype=np.uint64))
        self.assertEqual(int(counts["q"].item()),3)
        self.assertEqual(counts["p"].dtype,mx.uint64)
        self.assertEqual(counts["q"].dtype,mx.uint64)
        with self.assertRaisesRegex(ValueError,"COUNT_GEOMETRY_INVALID"):
            parity.native_uniform_step_counts(
                opt.state_dict(),{"p":p.data,"q":q.data},
                parameter_order=("p","q"),count_shapes={"p":(3,),"q":()})

    def test_historical_count_mapping_rejects_nonuniform_step_contract(self):
        import torch
        p=torch.nn.Parameter(torch.tensor([.2,.3],dtype=torch.float32))
        q=torch.nn.Parameter(torch.tensor([.4,.5],dtype=torch.float32))
        opt=torch.optim.AdamW([p,q],lr=.001)
        p.grad=torch.ones_like(p);q.grad=torch.ones_like(q);opt.step()
        state=opt.state_dict()
        state["state"][state["param_groups"][0]["params"][1]]["step"]=torch.tensor(2.)
        with self.assertRaisesRegex(ValueError,"STEPS_DISAGREE"):
            parity.native_uniform_step_counts(
                state,{"p":p.data,"q":q.data},parameter_order=("p","q"),
                count_shapes={"p":(),"q":()})


if __name__=="__main__":
    unittest.main()
