# MLX AdamW continuation: disposable fixture proof

**Scope:** synthetic FP32 arrays and one tiny synthetic transformer. No historical Bilqis student receives an optimizer update.

**Runtime observed on the test Mac:** Python with PyTorch 2.11.0 and MLX 0.31.1. The previous source checkpoint is `student-116760-7e9af4651f28.pt`, step 116760, and remains immutable.

## Results

- Converted native PyTorch AdamW parameter moments by original optimizer parameter order. Restored the fixture's step counter to **116760** before comparing continuation.
- Wrote a complete disposable MLX state to `model-and-own-adamw.safetensors`. A separate JSON manifest retains parameter order, source digest, beta coefficients, epsilon, weight decay, bias-correction mode and the file SHA-256.
- Reloaded all parameter and moment tensors, including dotted legacy parameter names, through an index-based tensor namespace. The restored step was **116760**.
- Applied four fixed gradients to both synthetic PyTorch and MLX optimizer states. All four resumed fixture steps through **116764** matched within **0.000001** absolute error; the separate pre-save direct-copy comparison observed zero parameter discrepancy.
- Rejected an attempt to overwrite the same bundle directory and detected a corrupted safetensors file before restoring state.
- Compared PyTorch and differentiable MLX forward/backward for a separate tiny one-block transformer, using real attention, tied embeddings and the same LayerNorm/squared-ReLU math as the historical model. Losses and per-parameter gradients matched within **0.0002** absolute error. Global-L2 gradient clipping also matched within **0.0002**.

Independent source guidance: [MLX AdamW](https://ml-explore.github.io/mlx/build/html/python/optimizers/_autosummary/mlx.optimizers.AdamW.html) documents the default `bias_correction=False`, which differs from native PyTorch AdamW. We explicitly enable bias correction. [MLX optimizer persistence](https://ml-explore.github.io/mlx/build/html/python/optimizers.html) notes that betas and epsilon are not stored in optimizer.state, so the manifest records them rather than assuming state-only persistence is complete.

## Reproduce without training the student

```sh
python3 -m unittest tests.test_mlx_checkpoint tests.test_mlx_gradients -v
npm run train -- --dry-run
```

These tests use temporary fixtures and do not touch the legacy checkpoint. The end-to-end MLX **production student** remains blocked: we have not proved full-network optimizer-gradient continuation on an independent copy, full-network save/reload, MPS versus GPU throughput, the live adaptive teacher, or the new grade-rubric admission. In particular, synthetic AdamW continuity is not a school graduation receipt.
