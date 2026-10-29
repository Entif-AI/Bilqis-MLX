# A02.2 complete B01 tensor-tree staging candidate

Disposition: SCOPED_IMPLEMENTATION_EGM_PENDING. This does not close
A02.2/#400 or authorize an optimizer, source release or checkpoint write.

The source-side bank candidate from A02.1 now has a complete
parameter-tree staging adapter in
bilqis_mlx/semantics/atlas_vocabulary_transaction.py.
FullVocabularyParent binds the exact B01 ModelTopologySpecV2,
GenerationExtents, complete FP32 parameter tree, native AdamW moments,
step and learning-rate scalars, and the source-bound bank slice.
The B01 serializer verifies every name, shape and moment before
allocation; bank slice references must be the same objects as the
complete parent tree, preventing caller-supplied split-brain banks.

The adapter checks a conservative full-checkpoint disk budget before
materializing new banks, then produces an immutable
PreparedVocabularyCandidate with the new complete B01 tensor tree,
active mask digest, allocation lineage and resource estimate.
All non-bank parameter objects and AdamW scalar objects are preserved;
old bank bytes and moments remain unchanged; new moments start at zero.
No legacy monolithic embedding.weight migration is used.

The optional full 80M-parameter disposable MLX witness was executed
with BILQIS_BAMF_FULL_WITNESS=1 and passed. It also proves a
below-budget candidate fails before materialization.

Remaining owner work: the existing Factory/admission transaction must
consume this typed candidate under a source-authorized admission
receipt, preserve rejection and crash/cold-resume state, and publish
one pointer only after full source/optimizer/retention proof. The
current historical runtime is not silently switched to BAMF.
