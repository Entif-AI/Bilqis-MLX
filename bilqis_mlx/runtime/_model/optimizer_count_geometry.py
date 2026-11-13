"""B12 optimizer-count geometry derived from the B01 parameter ledger."""
from bilqis_mlx.runtime.model_topology_v2 import Initializer, MATRIX_RANK


def declared_update_count_shape(item) -> tuple[int, ...]:
    """Return scalar or leading-row count geometry for one declared parameter."""
    table_initializers = {
        Initializer.IDENTITY_BANK,
        Initializer.MOTIF_PAGE,
        Initializer.FEATURE_TABLE,
    }
    rowwise = (
        item.initializer in table_initializers
        or (item.initializer is Initializer.EMBEDDING and len(item.shape) == MATRIX_RANK)
    )
    return (item.shape[0],) if rowwise else ()
