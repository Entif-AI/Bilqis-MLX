"""Historical Grade-A bootstrap authority.

Current runtime does not dispatch on this provider identity. It remains the
source-verification bootstrap for the accepted historical student lineage.
"""
from ..grade_a_release import AUTHORITY, accepted_grade_a

__all__ = ("AUTHORITY", "accepted_grade_a")
