"""Historical import compatibility for the pre-factory trainer module name.

The canonical runtime is :mod:`bilqis_mlx.trainer`. New code MUST import that
module directly. This shim intentionally owns no behavior or state.
"""
from . import trainer as _trainer

globals().update({name: value for name, value in vars(_trainer).items()
                  if not name.startswith("__")})

