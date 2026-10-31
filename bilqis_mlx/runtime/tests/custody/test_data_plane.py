"""Mirrored data-plane tests split by production ownership."""
from bilqis_mlx.runtime.tests.custody.data_plane.test_store import DataPlaneStoreTests as _Store
from bilqis_mlx.runtime.tests.custody.data_plane.test_custody import DataPlaneCustodyTests as _Custody
from bilqis_mlx.runtime.tests.custody.data_plane.test_events import DataPlaneEventTests as _Events

class DataPlaneStoreTests(_Store): pass
class DataPlaneCustodyTests(_Custody): pass
class DataPlaneEventTests(_Events): pass
