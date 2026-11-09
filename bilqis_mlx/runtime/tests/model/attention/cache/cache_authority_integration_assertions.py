"""Historical path retained as a non-authoritative tombstone.

The former C09/B13-to-B14 accepted-cache issuer assertions were removed after
fresh #917 EGM proved that the integration made the first caller the B14
policy/context owner. Native B14 authority behavior remains covered by the
test-only owner fixtures until a genuine production owner exists.
"""
