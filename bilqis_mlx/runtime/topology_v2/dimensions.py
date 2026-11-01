"""B01 dimensions ownership; historical tensor and initializer contracts retained."""
from __future__ import annotations
import hashlib
from .spec import ModelTopologySpecV2


MATRIX_RANK = 2

FEATURE_NONE_ROW = 1

FEATURE_RESERVED_ROWS = FEATURE_NONE_ROW + 1

FEATURE_ROWS = 512

FEATURE_DIM = 128

GRAPH_FEATURE_DIM = 64

MOTIF_CHANNELS = 128

SHA256_HEX_LENGTH = hashlib.sha256().digest_size * 2

IDENTITY_BANK_SHAPE = (ModelTopologySpecV2.semantic_bank_rows, ModelTopologySpecV2.width)

MOTIF_PAGE_SHAPE = (ModelTopologySpecV2.motif_page_rows, MOTIF_CHANNELS)
