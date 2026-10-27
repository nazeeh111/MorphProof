"""Thin adapter to a pinned, unmodified more-itertools function.

Contract for this experiment: one positional list of Python floats. The upstream
result type and exceptions are preserved, including int 0 for an empty list.
This is a function-level evaluation, not migration of the whole package.
"""
from pathlib import Path
import runpy

_original = runpy.run_path(str(Path(__file__).parent / "more_itertools" / "recipes.py"))["sum_of_squares"]


def sum_of_squares(values: list[float]) -> float:
    return _original(values)
