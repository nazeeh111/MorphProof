"""Thin adapter to a pinned, unmodified boltons mean implementation.

Contract for this experiment: one positional list of Python floats and the
upstream default 0.0 for empty input. No other Stats API is claimed supported.
"""
from pathlib import Path
import runpy

_original = runpy.run_path(str(Path(__file__).parent / "boltons" / "statsutils.py"))["mean"]


def mean(values: list[float]) -> float:
    return _original(values)
