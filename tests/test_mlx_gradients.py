"""Autodiff and global clipping parity on a disposable tiny transformer.

No historical Bilqis state is loaded, trained, or copied by this module.
"""
import unittest

import mlx.core as mx
import numpy as np
import torch
import torch.nn.functional as F

from bilqis_mlx.mlx_parity import forward_arrays, clip_gradients


class MlxGradientTests(unittest.TestCase):
    def test_tiny_causal_transformer_gradients_and_global_clip_match_pytorch(self):
        mx.set_default_device(mx.cpu)
        torch.set_num_threads(1)
        torch.manual_seed(109)
        d=12
        shapes={"embedding.weight":(24,d),"position.weight":(5,d),"norm.weight":(d,),
                "blocks.0.n1.weight":(d,),"blocks.0.n2.weight":(d,),
                "blocks.0.qkv.weight":(3*d,d),"blocks.0.proj.weight":(d,d),
                "blocks.0.up.weight":(24,d),"blocks.0.down.weight":(d,24)}
        original={name:torch.nn.Parameter(
                  (torch.randn(shape,dtype=torch.float32)*.05 if len(shape)>1
                   else torch.ones(shape,dtype=torch.float32)))
                  for name,shape in shapes.items()}
        new={name:mx.array(param.detach().numpy()) for name,param in original.items()}
        ids=np.array([[1,2,3,0],[4,5,6,7]],dtype=np.int32)
        lengths=[3,4]

        def torch_forward(weights):
            x=F.embedding(torch.tensor(ids).long(),weights['embedding.weight']) + \
              weights['position.weight'][:ids.shape[1]][None]
            norm=lambda z,w:F.layer_norm(z,(d,),w,None,1e-5)
            p='blocks.0.'
            h=norm(x,weights[p+'n1.weight'])
            q,k,v=F.linear(h,weights[p+'qkv.weight']).chunk(3,dim=-1)
            q,k,v=(t.reshape(2,4,3,4).transpose(1,2) for t in (q,k,v))
            attn=F.scaled_dot_product_attention(q,k,v,dropout_p=0,is_causal=True)
            x=x+F.linear(attn.transpose(1,2).reshape(2,4,d),weights[p+'proj.weight'])
            h=norm(x,weights[p+'n2.weight'])
            f=F.relu(F.linear(h,weights[p+'up.weight']))
            x=x+F.linear(f*f,weights[p+'down.weight'])
            x=norm(x,weights['norm.weight'])
            out=torch.stack([x[i,n-1] for i,n in enumerate(lengths)])
            return F.linear(out,weights['embedding.weight'][[6,7]])

        loss_t=torch_forward(original).square().mean()
        loss_t.backward()
        loss_m=lambda params:mx.mean(mx.square(forward_arrays(mx,params,ids,lengths,
                                             heads=3,layers=1,answer_ids=[6,7])))
        gradients=mx.grad(loss_m)(new)
        mx.eval(gradients)
        self.assertLessEqual(abs(float(loss_t.detach())-float(loss_m(new).item())),1e-5)
        for name in original:
            discrepancy=float(np.max(np.abs(original[name].grad.numpy()-
                                          np.asarray(gradients[name]))))
            self.assertLessEqual(discrepancy,2e-4,name)

        clipped,norm=clip_gradients(mx,gradients,max_norm=.001)
        torch_norm=torch.nn.utils.clip_grad_norm_(list(original.values()),max_norm=.001)
        mx.eval(clipped,norm)
        self.assertLessEqual(abs(float(norm.item())-float(torch_norm)),2e-4)
        for name in original:
            discrepancy=float(np.max(np.abs(original[name].grad.numpy()-
                                          np.asarray(clipped[name]))))
            self.assertLessEqual(discrepancy,2e-4,name)

    def test_empty_clipping_tree_and_invalid_max_norm_fail(self):
        with self.assertRaisesRegex(ValueError,'EMPTY_GRADIENT'):
            clip_gradients(mx,{},max_norm=1.)
        with self.assertRaisesRegex(ValueError,'INVALID_GRADIENT_CLIP'):
            clip_gradients(mx,{'w':mx.array([1.])},max_norm=0)

if __name__=='__main__':
    unittest.main()
