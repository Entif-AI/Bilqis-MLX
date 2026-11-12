"""Persistent BAMF human-run operator entrypoint."""
from .session import BamfOperatorResult, operate_bamf

__all__ = ("BamfOperatorResult", "operate_bamf")
