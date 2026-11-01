# Encountered model-directory interruption

The #484 structure guard reported _model16 baseline ->19 current, target<=12.
Feature WIP was preserved under local WorkStack1ceb5729-ffbd-46b8-8dd1-ec0a89eb230f
before changing ownership. Five existing production owners moved byte-for-byte:
cache codec/records into _model/cache; backbone group inputs/numerical/source
bridge into _model/backbone. The two cache test owners moved under mirrored
attention/cache. All seven moved files retain exact SHA256 bytes. Runtime search
roots preserve canonical bilqis_mlx.runtime module names and relative imports.
_model has12 direct Python files after the move. No recursive cleanup was done.

Before restoring #484 feature changes, attention/cache/backbone proof:44 passed,
zero skips. This is a structural checkpoint, not cache-policy or producer admission.
