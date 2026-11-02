"""Identify the retired numbered capability aliases in historical telemetry."""
import re


def is_historical_capability(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"G\d+", value) is not None
