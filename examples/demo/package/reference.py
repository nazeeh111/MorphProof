"""Explicit scalar reductions supported by the initial Rust backend.

Declared domain: Python lists of floats. Order and floating-point operations are
part of the contract. Exceptions on empty means are observable behavior.
"""


def sum_squares(values: list[float]) -> float:
    total = 0.0
    for value in values:
        total = total + value * value
    return total


def mean(values: list[float]) -> float:
    if len(values) == 0:
        raise ValueError("mean requires at least one value")
    total = 0.0
    for value in values:
        total = total + value
    return total / len(values)


def positive_energy(values: list[float]) -> float:
    total = 0.0
    for value in values:
        if value > 0.0:
            total = total + value * value
    return total
