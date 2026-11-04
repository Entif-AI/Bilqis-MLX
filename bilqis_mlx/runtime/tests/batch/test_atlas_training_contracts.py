"""Factory training contracts through the released adapter boundary."""

from bilqis_mlx.runtime.tests.test_atlas_training_adapter import (
    AtlasTrainingAdapterTest, BilqisError, replace, require_current_release,
)
from bilqis_mlx.runtime.atlas_training_contracts import BamfTrainingBatch


class TrainingContractsTests(AtlasTrainingAdapterTest):
    def test_current_release_is_checked_again_at_consumption(self):
        batch = self.compile(self.rows)
        require_current_release(batch, self.context, generation_binding=self.model_generation)
        with self.assertRaises(BilqisError):
            require_current_release(replace(batch, release_sha256='f' * 64), self.context, generation_binding=self.model_generation)
        with self.assertRaises(BilqisError):
            require_current_release(batch, self.context, generation_binding='stale-generation')
        with self.assertRaises(BilqisError):
            self.compile(self.rows, generation='stale-generation')

    def test_caller_cannot_construct_factory_training_batch(self):
        with self.assertRaises(BilqisError):
            BamfTrainingBatch("a" * 64, "b" * 64, "c" * 64, "A.TEST", ())
