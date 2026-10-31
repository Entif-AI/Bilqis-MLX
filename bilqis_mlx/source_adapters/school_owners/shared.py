"""Admitted finite-world, Boolean and numeric source adapters and independent checks."""
from __future__ import annotations

from ...curriculum import BOOLEAN_SIGNATURE_OPERAND_COUNT

from bilqis_mlx.errors import ErrorBus, SOURCE

from dataclasses import dataclass as _dataclass
from typing import Callable as _Callable
from ...grade_b_oracle import _direct_truth, evaluate as grade_b_gold, operand_truth
from ...live_grade_b import _u7c_pattern_counts

from ...factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from ...factory.autonomy import SupplementalEvidenceSpec
from ...factory.model import SourceAdapter
from ...curriculum import BOOLEAN_OPERATORS
from ..numeric import check_numeric, semantic_footprint as numeric_semantic_footprint
from ..structure import inspect_boolean_identification, inspect_source_query

from ...grade_a_oracle import VERSION as A_ORACLE


from ...live_grade_a import (GENERATOR as A_COHORT_GENERATOR, RELEASE as A_RELEASE,
                            generator_source_digest)
from ..grade_a_presentation import (
    IRRELEVANT_CONTEXT_VARIATION as A_IRRELEVANT_CONTEXT_VARIATION,
    MEMBER_CONTEXT_VARIATION as A_MEMBER_CONTEXT_VARIATION,
    constructor_digest as a_provider_digest,
    draw_a,
)


from ...grade_b_oracle import CONNECTIVES, VERSION as B_ORACLE

from ...boolean_composite import (
    CAPABILITY as B_COMPOSITE_CAPABILITY,
    GENERATOR as B_COMPOSITE_GENERATOR,
    ORACLE as B_COMPOSITE_ORACLE,
    RELEASE as B_COMPOSITE_RELEASE,
    constructor_digest as b_composite_digest,
    draw_composite,
)

from ...boolean_identification import (
    CAPABILITY as B_IDBOOLOPS_CAPABILITY,
    GENERATOR as B_IDBOOLOPS_GENERATOR,
    ORACLE as B_IDBOOLOPS_ORACLE,
    RELEASE as B_IDBOOLOPS_RELEASE,
    constructor_digest as b_idboolops_digest,
    draw_identification,
)


from ...live_grade_b import (GENERATOR as B_COHORT_GENERATOR, RELEASE as B_RELEASE,
                            draw_connectives, constructor_digest as b_digest)


from ...live_grade_c import (GENERATOR as C_COHORT_GENERATOR, RELEASE as C_RELEASE,
                            PLANS, constructor_digest as c_digest,
                            provider_implementation_digest as c_provider_digest)


from ...numeric_curriculum import ORACLE as C_ORACLE, draw_numeric


from ...numeric_staircase import RELEASE as STAIRCASE_RELEASE, constructor_digest as staircase_digest

from ...boolean_association import (
    VERSION as BOOLEAN_ASSOCIATION_OPTION,
    draw_b_grade_bridges,
)


BOOLEAN_RUNTIME_SAMPLER = "bilqis.mlx.grade-b-u7c-runtime-sampler/v3"
