"""Disposable MLX checkpoint fidelity; never updates historic Bilqis tensors."""
from pathlib import Path
import hashlib
import tempfile
import unittest

import numpy as np
import torch
import mlx.core as mx
from bilqis_mlx.mlx_checkpoint import save_new_bundle,load_bundle,load_semantically_bound_bundle
from bilqis_mlx.mlx_parity import native_optimizer_to_mlx


class MlxCheckpointTests(unittest.TestCase):
    def test_complete_fp32_moments_restart_then_four_steps_match_pytorch(self):
        mx.set_default_device(mx.cpu)
        torch.set_num_threads(1)
        p=torch.nn.Parameter(torch.tensor([[.5,-1.1],[2.3,.007]],dtype=torch.float32))
        q=torch.nn.Parameter(torch.tensor([-.2,.01,.7],dtype=torch.float32))
        pytorch=torch.optim.AdamW([p,q],lr=.00013,betas=(.9,.95),
                                  eps=1e-8,weight_decay=.01,foreach=False)
        p.grad=torch.tensor([[.2,-.4],[.01,.008]],dtype=torch.float32)
        q.grad=torch.tensor([-.1,.33,-.5],dtype=torch.float32)
        pytorch.step()  # This is a tiny fixture, not a live Bilqis student.
        for cell in pytorch.state.values():
            cell['step']=torch.tensor(float(116760))
        info,original_optimizer=native_optimizer_to_mlx(
            pytorch.state_dict(),{"embedding.weight":p.detach(),
                                 "blocks.0.qkv.weight":q.detach()},
            parameter_order=("embedding.weight","blocks.0.qkv.weight"))
        self.assertEqual(info["native_step"],116760)
        parameters={"embedding.weight":mx.array(p.detach().numpy()),
                    "blocks.0.qkv.weight":mx.array(q.detach().numpy())}
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)/"disposable-model"
            receipt=save_new_bundle(destination,parameters,original_optimizer,
                                    source_digest=hashlib.sha256(b"synthetic fixture").hexdigest(),
                                    reserve_gib=0)
            self.assertEqual(receipt['optimizer_step'],116760)
            self.assertEqual(receipt['tensor_count'],8)
            with self.assertRaisesRegex(ValueError,'NO_SEMANTIC_CATALOG'):
                load_semantically_bound_bundle(destination)
            with self.assertRaises(FileExistsError):
                save_new_bundle(destination,parameters,original_optimizer,
                    source_digest=receipt['source_digest'],reserve_gib=0)
            updated,optimizer,reloaded=load_bundle(destination)
            self.assertEqual(list(updated),list(parameters))
            self.assertTrue(optimizer.bias_correction)
            self.assertEqual(int(optimizer.state['step'].item()),116760)
            for j in range(1,5):
                gp=torch.tensor([[.2+.01*j,-.4],[.01,-.01*j]],dtype=torch.float32)
                gq=torch.tensor([-.1,.33+.01*j,-.5],dtype=torch.float32)
                p.grad=gp;q.grad=gq
                pytorch.step()
                optimizer.update(updated,{
                  'embedding.weight':mx.array(gp.numpy()),
                  'blocks.0.qkv.weight':mx.array(gq.numpy())})
                mx.eval(updated,optimizer.state)
                self.assertLessEqual(float(np.max(np.abs(p.detach().numpy()-
                                        np.asarray(updated['embedding.weight'])))),1e-6)
                self.assertLessEqual(float(np.max(np.abs(q.detach().numpy()-
                                        np.asarray(updated['blocks.0.qkv.weight'])))),1e-6)
                self.assertEqual(int(optimizer.state['step'].item()),116760+j)

    def test_tampered_checkpoint_detected_before_loading(self):
        import mlx.optimizers as optim
        mx.set_default_device(mx.cpu)
        weights={'w':mx.array([1.,-2.],dtype=mx.float32)}
        optimizer=optim.AdamW(learning_rate=.00013,bias_correction=True)
        optimizer.update(weights,{'w':mx.array([.1,.2],dtype=mx.float32)})
        mx.eval(weights,optimizer.state)
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"fixture"
            save_new_bundle(dest,weights,optimizer,source_digest='a'*64,reserve_gib=0)
            p=dest/'model-and-own-adamw.safetensors'
            with p.open('ab') as f:f.write(b'not part of the original checkpoint')
            with self.assertRaisesRegex(ValueError,'CORRUPTED'):
                load_bundle(dest)


if __name__=='__main__':
    unittest.main()
