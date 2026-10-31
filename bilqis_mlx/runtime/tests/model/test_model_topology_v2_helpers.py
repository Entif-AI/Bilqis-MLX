"""Shared fixtures extracted structurally from test_model_topology_v2.py."""
from __future__ import annotations
import json
import hashlib
from contextlib import redirect_stdout
from io import StringIO
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology import ModelTopologySpec
from bilqis_mlx.runtime.model_topology_v2 import (
    BAMF_ARCHITECTURE_ID, LEGACY_ARCHITECTURE_ID, ModelTopologySpecV2,
    GenerationExtents, GenerationProvenance, ParameterCategory, ParameterCensus, ParameterGroup, ParameterSpec, Initializer,
    bamf_parameter_census, print_bamf_parameter_census,
    bamf_deserialize_arrays, bamf_serialization_arrays, bamf_storage_key,
    deserialize_topology,
    expected_bamf_shapes, initialize_bamf_parameter, initialize_bamf_row, initializer_seed,
    project_identity_source_factor,
    validate_bamf_parameters,
)
from bilqis_mlx.runtime.topology_lifecycle import (
    construct_unbound_model, dispatch_model_factory, operator_topology, topology_from_file,
)

if __name__ == "__main__":
    unittest.main()
